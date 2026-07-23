import json
from typing import Any, Dict, List

from .clinical_gate import ClinicalApprovalGate, GateEvaluation
from .llm import GeminiFlashLiteClient, LLMError
from .models import EvidenceCitation, GuidanceDecision, GuidanceRequest, GuidanceResponse
from .retrieval import JsonlEvidenceRetriever
from .routing import CapabilityRouter


SYSTEM_INSTRUCTION = """당신은 Health Guidance Policy Engine이 허용한 범위만 설명하는 한국어 건강 안내 모델이다.
제공된 정책, 임상 승인 범위, 사용자 맥락, Evidence 밖의 의학적 사실을 만들지 않는다.
진단 확률, 치료, 약물, 운동 강도, 긴급도는 허용된 claim과 Evidence에 있을 때만 말한다.
반드시 JSON 객체로 답하고 answer, basis, uncertainty, next_actions 키를 포함한다.
인용 식별자는 새로 만들지 않는다."""


class GuidanceService:
    def __init__(
        self,
        router: CapabilityRouter,
        gate: ClinicalApprovalGate,
        retriever: JsonlEvidenceRetriever,
        llm: GeminiFlashLiteClient,
    ) -> None:
        self.router = router
        self.gate = gate
        self.retriever = retriever
        self.llm = llm

    def route(self, request: GuidanceRequest) -> GateEvaluation:
        capability_id = self.router.route(request)
        return self.gate.evaluate(request, capability_id)

    def respond(self, request: GuidanceRequest) -> GuidanceResponse:
        evaluation = self.route(request)
        if not evaluation.decision.allowed or request.dry_run:
            return GuidanceResponse(request_id=request.request_id, decision=evaluation.decision)

        evidence = self.retriever.retrieve(request.question, evaluation)
        if evaluation.capability.get("clinical_approval_required") and not evidence:
            decision = evaluation.decision.model_copy(
                update={
                    "allowed": False,
                    "action": "INSUFFICIENT_EVIDENCE",
                    "reason": "clinical approval exists but no approved evidence is retrievable",
                }
            )
            return GuidanceResponse(request_id=request.request_id, decision=decision)

        prompt = self._prompt(request, evaluation, evidence)
        generated = self.llm.generate_json(SYSTEM_INSTRUCTION, prompt)
        citations = [
            EvidenceCitation(
                evidence_id=item["evidence_id"],
                source_id=item["source_id"],
                source_locator=item["source_locator"],
                statement=item["normalized_statement"],
            )
            for item in evidence
        ]
        return GuidanceResponse(
            request_id=request.request_id,
            decision=evaluation.decision,
            answer=str(generated["answer"]),
            basis=self._string_list(generated.get("basis")),
            uncertainty=self._string_list(generated.get("uncertainty")),
            next_actions=self._string_list(generated.get("next_actions")),
            citations=citations,
            model=self.llm.model,
        )

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    @staticmethod
    def _prompt(request: GuidanceRequest, evaluation: GateEvaluation, evidence: List[Dict[str, Any]]) -> str:
        payload = {
            "question": request.question,
            "locale": request.locale,
            # User and conversation identifiers are deliberately excluded.
            "context": request.context,
            "capability": {
                "capability_id": evaluation.capability["capability_id"],
                "risk_level": evaluation.capability["risk_level"],
                "intended_outputs": evaluation.capability["intended_outputs"],
            },
            "policy": {
                "policy_id": (evaluation.policy or {}).get("policy_id"),
                "action": (evaluation.policy or {}).get("action"),
                "allowed_claims": (evaluation.policy or {}).get("allowed_claims", []),
                "prohibited_claims": (evaluation.policy or {}).get("prohibited_claims", []),
            },
            "clinical_approval": {
                "review_id": (evaluation.review or {}).get("review_id"),
                "protocol_version": (evaluation.review or {}).get("protocol_version"),
                "constraints": (evaluation.review or {}).get("constraints", []),
            },
            "evidence": [
                {
                    "evidence_id": item["evidence_id"],
                    "statement": item["normalized_statement"],
                    "population": item["population"],
                    "source_id": item["source_id"],
                    "source_locator": item["source_locator"],
                }
                for item in evidence
            ],
            "response_contract": {
                "answer": "string",
                "basis": ["string"],
                "uncertainty": ["string"],
                "next_actions": ["string"],
            },
        }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

