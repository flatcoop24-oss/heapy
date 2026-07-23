import re
from typing import Iterable

from .knowledge import KnowledgeRepository
from .models import GuidanceRequest


def _contains(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


class CapabilityRouter:
    """Conservative deterministic router; ambiguous medical requests route high."""

    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    def route(self, request: GuidanceRequest) -> str:
        if request.requested_capability_id:
            self.repository.capability(request.requested_capability_id)
            return request.requested_capability_id

        text = re.sub(r"\s+", " ", request.question.casefold()).strip()
        if _contains(text, ("응급", "119", "의식", "호흡곤란", "가슴 통증", "마비", "심한 출혈", "지금 바로 병원")):
            return "CAP_URGENCY_TRIAGE"

        medication_terms = ("약", "복용", "처방", "용량", "상호작용", "금기")
        medication_decision_terms = ("끊", "중단", "바꿔", "줄여", "늘려", "같이 먹", "먹어도", "용량")
        official_info_terms = ("효능", "주의사항", "부작용", "보관", "식약처", "설명서")
        if _contains(text, medication_terms):
            if _contains(text, official_info_terms) and not _contains(text, medication_decision_terms):
                return "CAP_OFFICIAL_DRUG_INFO"
            return "CAP_MEDICATION_DECISION_SUPPORT"

        exercise_terms = ("운동", "걷기", "근력", "스트레칭", "유산소", "재활")
        condition_terms = ("고혈압", "당뇨", "심장", "관절", "허리", "수술", "재활", "질환", "통증", "임신")
        if _contains(text, exercise_terms):
            if _contains(text, condition_terms):
                return "CAP_CONDITION_SPECIFIC_EXERCISE"
            return "CAP_GENERAL_WELLNESS"

        screening_terms = ("검진", "검사 결과", "혈당", "콜레스테롤", "ast", "alt", "혈압", "수치")
        record_terms = ("지난번", "추세", "기록", "올랐", "내렸", "변화")
        interpretation_terms = ("정상", "이상", "위험", "질환", "병", "재검", "어떻게 해야")
        if _contains(text, screening_terms):
            if _contains(text, record_terms) and not _contains(text, interpretation_terms):
                return "CAP_RECORDED_DATA_DISPLAY"
            return "CAP_SCREENING_INTERPRETATION"

        if _contains(text, ("치료", "재검", "시술", "수술", "관리 계획")):
            return "CAP_TREATMENT_GUIDANCE"
        return "CAP_DIAGNOSTIC_SUPPORT"
