import re
from typing import Any, Dict, List, Optional, Set

from .clinical_gate import GateEvaluation
from .knowledge import KnowledgeRepository


TOKEN_RE = re.compile(r"[0-9a-zA-Z가-힣_]+")


def _tokens(value: str) -> Set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(value) if len(token) > 1}


class JsonlEvidenceRetriever:
    """Small local retriever used before the same filters are moved to pgvector."""

    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository

    def retrieve(self, question: str, gate: GateEvaluation, limit: int = 5) -> List[Dict[str, Any]]:
        policy_ids = set((gate.policy or {}).get("evidence_ids", []))
        review_ids = set((gate.review or {}).get("evidence_ids", []))
        eligible_ids = policy_ids | review_ids
        candidates = self.repository.evidence_by_ids(eligible_ids)
        high_risk = gate.capability.get("clinical_approval_required") is True
        query_tokens = _tokens(question)
        scored = []
        for evidence in candidates:
            if evidence.get("status") != "ACTIVE" or evidence.get("embed") is not True:
                continue
            if high_risk and evidence.get("review_status") != "CLINICALLY_APPROVED":
                continue
            if not high_risk and evidence.get("review_status") not in {"SOURCE_VERIFIED", "CLINICALLY_APPROVED"}:
                continue
            haystack = " ".join(
                [
                    str(evidence.get("topic", "")),
                    str(evidence.get("normalized_statement", "")),
                    " ".join(evidence.get("keywords", [])),
                ]
            )
            overlap = len(query_tokens & _tokens(haystack))
            scored.append((overlap, evidence["evidence_id"], evidence))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in scored[: max(1, min(limit, 10))]]

