import io
import json
import base64
import os
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Sequence, Tuple
from uuid import uuid4

from PIL import Image

from .models import BoundingBox, OCRToken


class OCRBackendError(RuntimeError):
    pass


class OCRBackend(ABC):
    name = "base"

    @abstractmethod
    def extract(self, content: bytes, content_type: str) -> List[OCRToken]:
        raise NotImplementedError


class ClovaOCRBackend(OCRBackend):
    """NAVER Cloud CLOVA OCR V2 adapter.

    The invoke URL already includes the domain-specific `/infer` path. Secrets
    are read only from environment variables and are never included in errors.
    """

    name = "clova"
    content_formats = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "application/pdf": "pdf",
        "image/tiff": "tiff",
    }

    def __init__(
        self,
        invoke_url: str | None = None,
        secret: str | None = None,
        language: str | None = None,
        timeout_seconds: float | None = None,
        opener: Any = None,
    ) -> None:
        self.invoke_url = invoke_url if invoke_url is not None else os.getenv("CLOVA_OCR_INVOKE_URL", "")
        self.secret = secret if secret is not None else os.getenv("CLOVA_OCR_SECRET", "")
        self.language = language if language is not None else os.getenv("CLOVA_OCR_LANGUAGE", "ko")
        self.timeout_seconds = timeout_seconds or float(os.getenv("CLOVA_OCR_TIMEOUT_SECONDS", "30"))
        self._opener = opener or urllib.request.urlopen

    def extract(self, content: bytes, content_type: str) -> List[OCRToken]:
        if not self.invoke_url or not self.secret:
            raise OCRBackendError("CLOVA OCR is not configured")
        normalized_content, image_format = self._normalize_content(content, content_type)
        payload = {
            "version": "V2",
            "requestId": str(uuid4()),
            "timestamp": int(time.time() * 1000),
            "lang": self.language,
            "images": [
                {
                    "format": image_format,
                    "name": "health-document",
                    "data": base64.b64encode(normalized_content).decode("ascii"),
                }
            ],
        }
        request = urllib.request.Request(
            self.invoke_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-OCR-SECRET": self.secret,
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                raw_response = response.read()
        except urllib.error.HTTPError as exc:
            raise OCRBackendError("CLOVA OCR request was rejected (HTTP %s)" % exc.code) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise OCRBackendError("CLOVA OCR is unavailable") from exc
        try:
            response_payload = json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OCRBackendError("CLOVA OCR returned an invalid response") from exc
        return self._parse_response(response_payload)

    @classmethod
    def _normalize_content(cls, content: bytes, content_type: str) -> Tuple[bytes, str]:
        normalized_type = content_type.casefold()
        if normalized_type in cls.content_formats:
            return content, cls.content_formats[normalized_type]
        if normalized_type == "image/webp":
            try:
                image = Image.open(io.BytesIO(content)).convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue(), "png"
            except Exception as exc:
                raise OCRBackendError("invalid WEBP image") from exc
        raise OCRBackendError("unsupported CLOVA OCR content type")

    @staticmethod
    def _parse_response(payload: Dict[str, Any]) -> List[OCRToken]:
        tokens: List[OCRToken] = []
        images = payload.get("images")
        if not isinstance(images, list) or not images:
            raise OCRBackendError("CLOVA OCR response has no images")
        for default_page, image_result in enumerate(images, start=1):
            if image_result.get("inferResult") != "SUCCESS":
                raise OCRBackendError("CLOVA OCR could not recognize the document")
            converted = image_result.get("convertedImageInfo") or {}
            page = int(converted.get("pageIndex", default_page - 1)) + 1
            fields = image_result.get("fields") or []
            for field in fields:
                text = str(field.get("inferText") or "").strip()
                vertices = (field.get("boundingPoly") or {}).get("vertices") or []
                if not text or not vertices:
                    continue
                confidence = float(field.get("inferConfidence") or 0.0)
                tokens.append(
                    OCRToken(
                        text=text,
                        confidence=max(0.0, min(confidence, 1.0)),
                        page=page,
                        bbox=_box([[point.get("x", 0), point.get("y", 0)] for point in vertices]),
                    )
                )
        if not tokens:
            raise OCRBackendError("no text was detected")
        return tokens


class FixtureOCRBackend(OCRBackend):
    """Deterministic local backend for tests and UI development.

    Each UTF-8 line is treated as one high-confidence OCR line. It is never
    selected automatically in production configuration.
    """

    name = "fixture"

    def extract(self, content: bytes, content_type: str) -> List[OCRToken]:
        try:
            lines = [line.strip() for line in content.decode("utf-8").splitlines() if line.strip()]
        except UnicodeDecodeError as exc:
            raise OCRBackendError("fixture backend requires UTF-8 text") from exc
        return [
            OCRToken(
                text=line,
                confidence=0.995,
                page=1,
                bbox=BoundingBox(x1=0, y1=index * 30, x2=1000, y2=index * 30 + 24),
            )
            for index, line in enumerate(lines)
        ]


def _result_payload(result: Any) -> Dict[str, Any]:
    payload = getattr(result, "json", result)
    if callable(payload):
        payload = payload()
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict) and "res" in payload and isinstance(payload["res"], dict):
        return payload["res"]
    if isinstance(payload, dict):
        return payload
    return {}


def _box(values: Sequence[Any]) -> BoundingBox:
    if len(values) == 4 and not isinstance(values[0], (list, tuple)):
        x1, y1, x2, y2 = [float(value) for value in values]
    else:
        points = values
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    return BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)


class PaddleOCRBackend(OCRBackend):
    """Lazy, entirely local PaddleOCR adapter supporting v2 and v3 outputs."""

    name = "paddle"

    def __init__(self) -> None:
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise OCRBackendError(
                    "PaddleOCR is not installed; install requirements-ocr-paddle.txt"
                ) from exc
            self._engine = PaddleOCR(
                lang="korean",
                use_doc_orientation_classify=True,
                use_doc_unwarping=True,
                use_textline_orientation=True,
            )
        return self._engine

    def extract(self, content: bytes, content_type: str) -> List[OCRToken]:
        pages = self._render_pages(content, content_type)
        engine = self._get_engine()
        tokens: List[OCRToken] = []
        for page_number, page in enumerate(pages, start=1):
            try:
                results = engine.predict(page)
                tokens.extend(self._parse_v3(results, page_number))
            except AttributeError:
                results = engine.ocr(page, cls=True)
                tokens.extend(self._parse_legacy(results, page_number))
        if not tokens:
            raise OCRBackendError("no text was detected")
        return tokens

    @staticmethod
    def _render_pages(content: bytes, content_type: str) -> List[Any]:
        import numpy as np

        if content_type == "application/pdf":
            try:
                import pypdfium2 as pdfium
            except ImportError as exc:
                raise OCRBackendError("PDF input requires pypdfium2") from exc
            document = pdfium.PdfDocument(content)
            return [
                np.asarray(page.render(scale=2).to_pil().convert("RGB"))
                for page in document
            ]
        try:
            image = Image.open(io.BytesIO(content)).convert("RGB")
        except Exception as exc:
            raise OCRBackendError("invalid or unsupported image") from exc
        return [np.asarray(image)]

    @staticmethod
    def _parse_legacy(results: Any, page: int) -> List[OCRToken]:
        tokens: List[OCRToken] = []
        for page_result in results or []:
            for line in page_result or []:
                if len(line) < 2:
                    continue
                box, recognition = line[0], line[1]
                text, confidence = recognition[0], recognition[1]
                if str(text).strip():
                    tokens.append(
                        OCRToken(
                            text=str(text).strip(),
                            confidence=float(confidence),
                            page=page,
                            bbox=_box(box),
                        )
                    )
        return tokens

    @staticmethod
    def _parse_v3(results: Iterable[Any], page: int) -> List[OCRToken]:
        tokens: List[OCRToken] = []
        for result in results or []:
            payload = _result_payload(result)
            texts = payload.get("rec_texts") or []
            scores = payload.get("rec_scores") or []
            boxes = payload.get("rec_boxes") or payload.get("dt_polys") or []
            for text, score, box in zip(texts, scores, boxes):
                if str(text).strip():
                    tokens.append(
                        OCRToken(
                            text=str(text).strip(),
                            confidence=float(score),
                            page=page,
                            bbox=_box(box),
                        )
                    )
        return tokens


class PaddleOCRVLBackend(PaddleOCRBackend):
    """Local PaddleOCR-VL document parser adapter.

    The VLM returns reading-order blocks. Markdown table rows are split back
    into evidence lines so the deterministic health-field validator remains
    the authority for values and units.
    """

    name = "paddle_vl"

    def _get_engine(self):
        if self._engine is None:
            try:
                from paddleocr import PaddleOCRVL
            except ImportError as exc:
                raise OCRBackendError(
                    "PaddleOCR-VL is not installed; install requirements-ocr-paddle.txt"
                ) from exc
            self._engine = PaddleOCRVL(
                use_doc_orientation_classify=True,
                use_doc_unwarping=True,
            )
        return self._engine

    def extract(self, content: bytes, content_type: str) -> List[OCRToken]:
        pages = self._render_pages(content, content_type)
        engine = self._get_engine()
        tokens: List[OCRToken] = []
        for page_number, page in enumerate(pages, start=1):
            results = engine.predict(page, format_block_content=True)
            tokens.extend(self._parse_vl(results, page_number))
        if not tokens:
            raise OCRBackendError("no document content was detected")
        return tokens

    @staticmethod
    def _parse_vl(results: Iterable[Any], page: int) -> List[OCRToken]:
        tokens: List[OCRToken] = []
        for result in results or []:
            payload = _result_payload(result)
            for block in payload.get("parsing_res_list") or []:
                content = str(block.get("block_content") or "").strip()
                bbox_values = block.get("block_bbox")
                if not content or not bbox_values:
                    continue
                bbox = _box(bbox_values)
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                if not lines:
                    continue
                line_height = max((bbox.y2 - bbox.y1) / len(lines), 1.0)
                for index, line in enumerate(lines):
                    # Markdown separator rows contain no health value.
                    if re_full_markdown_separator(line):
                        continue
                    tokens.append(
                        OCRToken(
                            text=line,
                            # Block outputs do not expose recognition confidence.
                            # Keep this below the auto-validation threshold.
                            confidence=0.90,
                            page=page,
                            bbox=BoundingBox(
                                x1=bbox.x1,
                                y1=bbox.y1 + index * line_height,
                                x2=bbox.x2,
                                y2=min(bbox.y2, bbox.y1 + (index + 1) * line_height),
                            ),
                        )
                    )
        return tokens


def re_full_markdown_separator(line: str) -> bool:
    compact = line.replace("|", "").replace(":", "").replace("-", "").strip()
    return not compact


def build_backend(name: str) -> OCRBackend:
    normalized = name.strip().casefold()
    if normalized == "fixture":
        return FixtureOCRBackend()
    if normalized == "clova":
        return ClovaOCRBackend()
    if normalized == "paddle":
        return PaddleOCRBackend()
    if normalized == "paddle_vl":
        return PaddleOCRVLBackend()
    raise ValueError("unsupported OCR backend: %s" % name)
