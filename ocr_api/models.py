from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    AUTO_VALIDATED = "AUTO_VALIDATED"
    USER_CONFIRMED = "USER_CONFIRMED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class BoundingBox(BaseModel):
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(ge=0)
    y2: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_order(self) -> "BoundingBox":
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("bounding box coordinates are reversed")
        return self


class OCRToken(BaseModel):
    text: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    page: int = Field(ge=1)
    bbox: BoundingBox


class ReferenceRange(BaseModel):
    raw: Optional[str] = None
    lower: Optional[float] = None
    upper: Optional[float] = None


class ObservationQuality(BaseModel):
    validation_passed: bool = False
    verification_status: VerificationStatus = VerificationStatus.REVIEW_REQUIRED
    extraction_confidence: float = Field(ge=0, le=1)
    review_reasons: List[str] = Field(default_factory=list)


class ScreeningObservation(BaseModel):
    observation_id: UUID = Field(default_factory=uuid4)
    item_code: Optional[str] = None
    raw_item_name: str
    value_numeric: Optional[float] = None
    value_text: Optional[str] = None
    raw_unit: Optional[str] = None
    normalized_unit: Optional[str] = None
    reference_range: ReferenceRange = Field(default_factory=ReferenceRange)
    reported_flag: Optional[str] = None
    evidence_text: str
    page: int = Field(ge=1)
    bbox: BoundingBox
    quality: ObservationQuality
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_value(self) -> "ScreeningObservation":
        if self.value_numeric is None and not self.value_text:
            raise ValueError("numeric or text value is required")
        return self


class ReportMetadata(BaseModel):
    report_id: UUID = Field(default_factory=uuid4)
    client_user_id: Optional[str] = None
    screened_on: Optional[date] = None
    provider_name: Optional[str] = None
    source_method: str = "OCR"
    source_checksum_sha256: str
    parser_version: str
    verification_status: VerificationStatus = VerificationStatus.REVIEW_REQUIRED


class OCRResult(BaseModel):
    schema_version: str = "1.0"
    report: ReportMetadata
    observations: List[ScreeningObservation]
    warnings: List[str] = Field(default_factory=list)


class OCRJob(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    result: Optional[OCRResult] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ObservationCorrection(BaseModel):
    observation_id: UUID
    value_numeric: Optional[float] = None
    value_text: Optional[str] = None
    raw_unit: Optional[str] = None

    @model_validator(mode="after")
    def require_corrected_value(self) -> "ObservationCorrection":
        if self.value_numeric is None and not self.value_text:
            raise ValueError("corrected numeric or text value is required")
        return self


class ConfirmationRequest(BaseModel):
    accepted_observation_ids: List[UUID] = Field(default_factory=list)
    corrections: List[ObservationCorrection] = Field(default_factory=list)

