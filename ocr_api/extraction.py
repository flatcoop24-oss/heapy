import re
from statistics import mean
from typing import Iterable, List, Optional, Sequence, Tuple

from .dictionary import ItemDefinition, ScreeningDictionary, normalize_label
from .models import (
    BoundingBox,
    OCRToken,
    ObservationQuality,
    ReferenceRange,
    ScreeningObservation,
    VerificationStatus,
)


NUMBER_RE = re.compile(r"(?<![0-9.])[-+]?\d+(?:[.,]\d+)?")
RANGE_RE = re.compile(r"([-+]?\d+(?:[.,]\d+)?)\s*(?:~|～|−|–|—|-)\s*([-+]?\d+(?:[.,]\d+)?)")
FLAG_RE = re.compile(r"(?:^|\s)(H|L|N|HIGH|LOW|정상|이상)(?:$|\s)", re.IGNORECASE)
TEXT_VALUES = ("음성", "양성", "약양성", "흔적", "정상", "비정상", "negative", "positive", "trace")


def _float(value: str) -> float:
    return float(value.replace(",", ""))


def group_tokens_into_lines(tokens: Iterable[OCRToken]) -> List[List[OCRToken]]:
    grouped: List[List[OCRToken]] = []
    for page in sorted({token.page for token in tokens}):
        page_tokens = sorted(
            (token for token in tokens if token.page == page),
            key=lambda token: ((token.bbox.y1 + token.bbox.y2) / 2, token.bbox.x1),
        )
        for token in page_tokens:
            center = (token.bbox.y1 + token.bbox.y2) / 2
            target = None
            for line in reversed(grouped):
                if line[0].page != page:
                    break
                line_center = mean((item.bbox.y1 + item.bbox.y2) / 2 for item in line)
                line_height = max(item.bbox.y2 - item.bbox.y1 for item in line)
                if abs(center - line_center) <= max(8.0, line_height * 0.55):
                    target = line
                    break
            if target is None:
                grouped.append([token])
            else:
                target.append(token)
        for line in grouped:
            line.sort(key=lambda token: token.bbox.x1)
    return grouped


def _union_box(tokens: Sequence[OCRToken]) -> BoundingBox:
    return BoundingBox(
        x1=min(token.bbox.x1 for token in tokens),
        y1=min(token.bbox.y1 for token in tokens),
        x2=max(token.bbox.x2 for token in tokens),
        y2=max(token.bbox.y2 for token in tokens),
    )


def _parse_reference(text: str) -> ReferenceRange:
    match = RANGE_RE.search(text)
    if match:
        return ReferenceRange(raw=match.group(0), lower=_float(match.group(1)), upper=_float(match.group(2)))
    return ReferenceRange()


def _find_unit(text: str, canonical: Optional[str]) -> Optional[str]:
    if canonical:
        candidates = {canonical, canonical.replace("2", "²")}
        for candidate in candidates:
            match = re.search(re.escape(candidate), text, re.IGNORECASE)
            if match:
                return match.group(0)
    match = re.search(r"(?:mg|g|kg|mmol|mL|µg|ug|U)/(?:dL|L|min(?:/1[.,]73m[²2])?)|mmHg|cm|kg/m[²2]|%", text, re.IGNORECASE)
    return match.group(0) if match else None


def _value_after_label(text: str, item: ItemDefinition) -> Tuple[Optional[float], Optional[str]]:
    parts = [part.strip() for part in text.split("|")]
    value_area = parts[1] if len(parts) > 1 else text
    numeric = NUMBER_RE.search(value_area)
    if numeric:
        return _float(numeric.group(0)), None
    normalized = normalize_label(value_area)
    for candidate in TEXT_VALUES:
        if normalize_label(candidate) in normalized:
            return None, candidate
    if item.value_type in {"CODE", "TEXT"} and value_area.strip():
        return None, value_area.strip()
    return None, None


def _validate(item: ItemDefinition, value_numeric: Optional[float], value_text: Optional[str], unit: Optional[str], confidence: float) -> ObservationQuality:
    reasons: List[str] = []
    if value_numeric is None and not value_text:
        reasons.append("VALUE_MISSING")
    if confidence < 0.95:
        reasons.append("LOW_OCR_CONFIDENCE")
    if item.value_type == "NUMERIC" and not unit:
        reasons.append("UNIT_MISSING")
    if item.canonical_unit and unit:
        if normalize_label(item.canonical_unit) != normalize_label(unit):
            reasons.append("UNIT_MISMATCH")
    # OCR-origin values always require explicit user confirmation before use.
    return ObservationQuality(
        validation_passed=not reasons,
        verification_status=VerificationStatus.REVIEW_REQUIRED,
        extraction_confidence=confidence,
        review_reasons=reasons or ["USER_CONFIRMATION_REQUIRED"],
    )


def extract_observations(tokens: List[OCRToken], dictionary: ScreeningDictionary) -> Tuple[List[ScreeningObservation], List[str]]:
    observations: List[ScreeningObservation] = []
    warnings: List[str] = []
    for line_tokens in group_tokens_into_lines(tokens):
        evidence = " ".join(token.text for token in line_tokens)
        item = dictionary.match(evidence.split("|", 1)[0] if "|" in evidence else evidence)
        if item is None:
            continue
        value_numeric, value_text = _value_after_label(evidence, item)
        if value_numeric is None and not value_text:
            warnings.append("값을 찾지 못한 행: %s" % evidence)
            continue
        confidence = min(token.confidence for token in line_tokens)
        unit = _find_unit(evidence, item.canonical_unit)
        reference_text = "|".join(evidence.split("|")[3:4]) if evidence.count("|") >= 3 else evidence
        flag_match = FLAG_RE.search(evidence)
        observations.append(
            ScreeningObservation(
                item_code=item.item_code,
                raw_item_name=item.display_name,
                value_numeric=value_numeric,
                value_text=value_text,
                raw_unit=unit,
                normalized_unit=item.canonical_unit if unit else None,
                reference_range=_parse_reference(reference_text),
                reported_flag=flag_match.group(1).upper() if flag_match else None,
                evidence_text=evidence,
                page=line_tokens[0].page,
                bbox=_union_box(line_tokens),
                quality=_validate(item, value_numeric, value_text, unit, confidence),
                raw_payload={"backend_tokens": [token.model_dump() for token in line_tokens]},
            )
        )
    if not observations:
        warnings.append("지원되는 건강검진 항목을 추출하지 못했습니다.")
    return observations, warnings

