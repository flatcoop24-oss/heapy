import hashlib
import threading
from copy import deepcopy
from datetime import date
from typing import Dict, Optional
from uuid import UUID

from .backends import OCRBackend, OCRBackendError
from .dictionary import ScreeningDictionary
from .extraction import extract_observations
from .models import (
    ConfirmationRequest,
    JobStatus,
    OCRJob,
    OCRResult,
    ReportMetadata,
    VerificationStatus,
    utc_now,
)


class JobNotFound(KeyError):
    pass


class JobConflict(RuntimeError):
    pass


class OCRService:
    parser_version = "health-screening-ocr.2"

    def __init__(self, backend: OCRBackend, dictionary: Optional[ScreeningDictionary] = None):
        self.backend = backend
        self.dictionary = dictionary or ScreeningDictionary.load_default()
        self._jobs: Dict[UUID, OCRJob] = {}
        self._payloads: Dict[UUID, bytes] = {}
        self._content_types: Dict[UUID, str] = {}
        self._metadata: Dict[UUID, Dict[str, object]] = {}
        self._lock = threading.RLock()

    def submit(
        self,
        content: bytes,
        content_type: str,
        client_user_id: Optional[str] = None,
        screened_on: Optional[date] = None,
        provider_name: Optional[str] = None,
    ) -> OCRJob:
        job = OCRJob()
        with self._lock:
            self._jobs[job.job_id] = job
            self._payloads[job.job_id] = content
            self._content_types[job.job_id] = content_type
            self._metadata[job.job_id] = {
                "client_user_id": client_user_id,
                "screened_on": screened_on,
                "provider_name": provider_name,
                "checksum": hashlib.sha256(content).hexdigest(),
            }
        return deepcopy(job)

    def process(self, job_id: UUID) -> None:
        with self._lock:
            job = self._require(job_id)
            job.status = JobStatus.PROCESSING
            job.updated_at = utc_now()
            content = self._payloads[job_id]
            content_type = self._content_types[job_id]
            metadata = self._metadata[job_id]
        try:
            tokens = self.backend.extract(content, content_type)
            observations, warnings = extract_observations(tokens, self.dictionary)
            result = OCRResult(
                report=ReportMetadata(
                    client_user_id=metadata["client_user_id"],
                    screened_on=metadata["screened_on"],
                    provider_name=metadata["provider_name"],
                    source_checksum_sha256=str(metadata["checksum"]),
                    parser_version=self.parser_version + "+" + self.backend.name,
                ),
                observations=observations,
                warnings=warnings,
            )
            with self._lock:
                job = self._require(job_id)
                job.result = result
                job.status = JobStatus.COMPLETED
                job.updated_at = utc_now()
        except OCRBackendError as exc:
            self._fail(job_id, "OCR_BACKEND_ERROR", str(exc))
        except Exception:
            # Do not reflect exceptions that may contain OCR text or health data.
            self._fail(job_id, "OCR_PROCESSING_ERROR", "document processing failed")
        finally:
            # Source files contain sensitive health data. Discard bytes after processing.
            with self._lock:
                self._payloads.pop(job_id, None)
                self._content_types.pop(job_id, None)

    def get(self, job_id: UUID) -> OCRJob:
        with self._lock:
            return deepcopy(self._require(job_id))

    def confirm(self, job_id: UUID, request: ConfirmationRequest) -> OCRResult:
        with self._lock:
            job = self._require(job_id)
            if job.status != JobStatus.COMPLETED or job.result is None:
                raise JobConflict("job has no completed result")
            observations = {item.observation_id: item for item in job.result.observations}
            requested_ids = set(request.accepted_observation_ids)
            requested_ids.update(item.observation_id for item in request.corrections)
            unknown = requested_ids.difference(observations)
            if unknown:
                raise JobConflict("unknown observation IDs: %s" % sorted(str(item) for item in unknown))
            for observation_id in request.accepted_observation_ids:
                observations[observation_id].quality.verification_status = VerificationStatus.USER_CONFIRMED
            for correction in request.corrections:
                observation = observations[correction.observation_id]
                observation.raw_payload["pre_confirmation_value"] = {
                    "value_numeric": observation.value_numeric,
                    "value_text": observation.value_text,
                    "raw_unit": observation.raw_unit,
                }
                observation.value_numeric = correction.value_numeric
                observation.value_text = correction.value_text
                observation.raw_unit = correction.raw_unit
                observation.normalized_unit = correction.raw_unit
                observation.quality.verification_status = VerificationStatus.USER_CONFIRMED
                observation.quality.review_reasons = []
                observation.quality.validation_passed = True
            if observations and all(
                item.quality.verification_status == VerificationStatus.USER_CONFIRMED
                for item in observations.values()
            ):
                job.result.report.verification_status = VerificationStatus.USER_CONFIRMED
            job.updated_at = utc_now()
            return deepcopy(job.result)

    def _fail(self, job_id: UUID, code: str, message: str) -> None:
        with self._lock:
            job = self._require(job_id)
            job.status = JobStatus.FAILED
            job.error_code = code
            job.error_message = message
            job.updated_at = utc_now()

    def _require(self, job_id: UUID) -> OCRJob:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise JobNotFound(str(job_id)) from exc
