import json
import unittest
from datetime import date

from guidance_api.clinical_gate import ClinicalApprovalGate
from guidance_api.knowledge import KnowledgeRepository
from guidance_api.llm import GeminiFlashLiteClient
from guidance_api.models import GuidanceRequest
from guidance_api.retrieval import JsonlEvidenceRetriever
from guidance_api.routing import CapabilityRouter
from guidance_api.service import GuidanceService


class FakeLLM:
    model = "gemini-3.5-flash-lite"

    def __init__(self):
        self.calls = []

    def generate_json(self, system_instruction, prompt):
        self.calls.append((system_instruction, json.loads(prompt)))
        return {
            "answer": "승인된 근거 범위의 테스트 답변입니다.",
            "basis": ["승인 근거"],
            "uncertainty": ["입력 범위 밖은 평가하지 않음"],
            "next_actions": ["승인 프로토콜의 다음 행동"],
        }


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class GuidanceCoreTest(unittest.TestCase):
    def setUp(self):
        self.repository = KnowledgeRepository()
        self.router = CapabilityRouter(self.repository)

    def test_router_sends_condition_exercise_and_emergency_to_high_risk(self):
        exercise = GuidanceRequest(question="고혈압에 맞는 운동 강도를 정해줘")
        emergency = GuidanceRequest(question="호흡곤란이 있는데 지금 응급실 가야 해?")
        self.assertEqual("CAP_CONDITION_SPECIFIC_EXERCISE", self.router.route(exercise))
        self.assertEqual("CAP_URGENCY_TRIAGE", self.router.route(emergency))

    def test_pending_high_risk_capability_does_not_call_llm(self):
        fake_llm = FakeLLM()
        service = GuidanceService(
            self.router,
            ClinicalApprovalGate(self.repository, as_of=date(2026, 7, 23)),
            JsonlEvidenceRetriever(self.repository),
            fake_llm,
        )
        response = service.respond(
            GuidanceRequest(
                question="검진 결과 위험도와 다음 검사를 알려줘",
                requested_capability_id="CAP_SCREENING_INTERPRETATION",
                context={
                    "verified_result": True,
                    "reference_or_rule_version": "2026-6",
                    "demographics": {"age": 40},
                    "relevant_history": [],
                    "current_symptoms": [],
                },
            )
        )
        self.assertFalse(response.decision.allowed)
        self.assertEqual("CLINICAL_REVIEW_REQUIRED", response.decision.action)
        self.assertEqual([], fake_llm.calls)

    def test_clinically_approved_high_risk_capability_can_answer(self):
        capability = self.repository.capabilities["CAP_SCREENING_INTERPRETATION"]
        capability.update(activation_status="CLINICALLY_APPROVED", status="ACTIVE")
        review = self.repository.reviews["REVIEW_SCREENING_INTERPRETATION_V2"]
        review.update(
            decision="APPROVED",
            reviewer_refs=["clinician:test-reviewer"],
            decision_rationale="test approval",
            protocol_version="screening-protocol.2",
            evidence_version="screening-evidence.2",
            decision_at="2026-07-01",
            valid_from="2026-07-01",
            valid_until="2027-06-30",
        )
        policy = self.repository.policies["SCREENING_INTERPRETATION_001"]
        policy.update(review_status="CLINICALLY_APPROVED", status="ACTIVE")
        for evidence_id in review["evidence_ids"]:
            self.repository.evidence[evidence_id].update(
                review_status="CLINICALLY_APPROVED",
                embed=True,
            )

        fake_llm = FakeLLM()
        service = GuidanceService(
            self.router,
            ClinicalApprovalGate(self.repository, as_of=date(2026, 7, 23)),
            JsonlEvidenceRetriever(self.repository),
            fake_llm,
        )
        response = service.respond(
            GuidanceRequest(
                question="검진 결과 위험도와 다음 검사를 알려줘",
                requested_capability_id="CAP_SCREENING_INTERPRETATION",
                context={
                    "verified_result": True,
                    "reference_or_rule_version": "2026-6",
                    "demographics": {"age": 40},
                    "relevant_history": [],
                    "current_symptoms": [],
                },
            )
        )
        self.assertTrue(response.decision.allowed)
        self.assertEqual("PROVIDE_CLINICAL_ASSESSMENT", response.decision.action)
        self.assertEqual("REVIEW_SCREENING_INTERPRETATION_V2", response.decision.clinical_review_id)
        self.assertEqual(2, len(response.citations))
        self.assertEqual(1, len(fake_llm.calls))
        prompt = fake_llm.calls[0][1]
        self.assertNotIn("user_id", prompt)
        self.assertEqual("screening-protocol.2", prompt["clinical_approval"]["protocol_version"])

    def test_general_exercise_uses_source_verified_evidence(self):
        fake_llm = FakeLLM()
        service = GuidanceService(
            self.router,
            ClinicalApprovalGate(self.repository),
            JsonlEvidenceRetriever(self.repository),
            fake_llm,
        )
        response = service.respond(
            GuidanceRequest(
                question="오늘 집에서 20분 운동 추천해줘",
                context={
                    "population": "GENERAL_ADULT",
                    "available_time": 20,
                    "location": "HOME",
                    "preferred_intensity": "LIGHT",
                    "current_health_limitation": False,
                },
            )
        )
        self.assertTrue(response.decision.allowed)
        self.assertEqual("ANSWER_GENERAL", response.decision.action)
        self.assertEqual(3, len(response.citations))


class GeminiAdapterTest(unittest.TestCase):
    def test_uses_flash_lite_and_json_contract(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["headers"] = dict(request.header_items())
            return FakeResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "answer": "테스트",
                                                "basis": [],
                                                "uncertainty": [],
                                                "next_actions": [],
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            )

        client = GeminiFlashLiteClient(api_key="test-key", opener=opener)
        result = client.generate_json("system", "prompt")
        self.assertIn("gemini-3.5-flash-lite:generateContent", captured["url"])
        self.assertEqual("application/json", captured["payload"]["generationConfig"]["responseMimeType"])
        self.assertEqual("test-key", captured["headers"]["X-goog-api-key"])
        self.assertEqual("테스트", result["answer"])


if __name__ == "__main__":
    unittest.main()
