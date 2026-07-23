import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/validate_guidance_knowledge.py"

spec = importlib.util.spec_from_file_location("validate_guidance_knowledge", SCRIPT_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


def load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class GuidanceKnowledgeTest(unittest.TestCase):
    def test_guidance_knowledge_is_valid(self):
        errors, counts = validator.validate()
        self.assertEqual([], errors)
        self.assertEqual(
            {
                "sources": 7,
                "evidence": 7,
                "embedded_evidence": 4,
                "policies": 19,
                "capabilities": 9,
                "clinical_reviews": 6,
                "templates": 11,
                "evaluation_cases": 18,
            },
            counts,
        )

    def test_only_general_exercise_evidence_is_embedded_in_v02(self):
        embedded = []
        for path in sorted((ROOT / "knowledge/evidence").glob("*.jsonl")):
            embedded.extend(record for record in load_jsonl(path) if record["embed"])
        self.assertEqual(
            {
                "WHO_PA_GENERAL_001",
                "WHO_PA_GENERAL_002",
                "WHO_PA_ADULT_001",
                "WHO_PA_SCOPE_001",
            },
            {record["evidence_id"] for record in embedded},
        )
        self.assertTrue(all(not record["medical_interpretation_required"] for record in embedded))

    def test_active_documents_have_no_slack_sources(self):
        sources = load_jsonl(ROOT / "knowledge/sources/source_documents.jsonl")
        for source in sources:
            if source["status"] == "ACTIVE" and source.get("url"):
                self.assertNotIn("slack.com", source["url"])

    def test_no_high_risk_capability_activates_without_clinical_approval(self):
        capabilities = load_jsonl(ROOT / "knowledge/capabilities/clinical_capabilities.jsonl")
        reviews = load_jsonl(ROOT / "knowledge/reviews/clinical_reviews.jsonl")
        approved_capabilities = {
            review["capability_id"]
            for review in reviews
            if review["decision"] == "APPROVED" and review["status"] == "ACTIVE"
        }
        for capability in capabilities:
            if capability["clinical_approval_required"]:
                self.assertNotEqual("ACTIVE_SOURCE_VERIFIED", capability["activation_status"])
                if capability["activation_status"] == "CLINICALLY_APPROVED":
                    self.assertIn(capability["capability_id"], approved_capabilities)

    def test_clinical_scope_is_designed_not_prohibited(self):
        capabilities = load_jsonl(ROOT / "knowledge/capabilities/clinical_capabilities.jsonl")
        capability_ids = {record["capability_id"] for record in capabilities}
        self.assertTrue(
            {
                "CAP_DIAGNOSTIC_SUPPORT",
                "CAP_TREATMENT_GUIDANCE",
                "CAP_CONDITION_SPECIFIC_EXERCISE",
                "CAP_SCREENING_INTERPRETATION",
                "CAP_MEDICATION_DECISION_SUPPORT",
                "CAP_URGENCY_TRIAGE",
            }.issubset(capability_ids)
        )

    def test_general_exercise_policy_uses_only_embedded_evidence(self):
        policies = load_jsonl(ROOT / "knowledge/policies/exercise.jsonl")
        general = next(policy for policy in policies if policy["policy_id"] == "EXERCISE_GENERAL_001")
        self.assertEqual(
            ["WHO_PA_GENERAL_001", "WHO_PA_GENERAL_002", "WHO_PA_ADULT_001"],
            general["evidence_ids"],
        )
        self.assertIn("condition_specific_treatment", general["prohibited_claims"])
        self.assertIn("medical_intensity_without_protocol", general["prohibited_claims"])

    def test_gold_cases_are_never_named_as_training_data(self):
        cases = load_jsonl(ROOT / "knowledge/evaluations/policy_baseline.jsonl")
        gold = [case for case in cases if case["split"] == "GOLD_TEST"]
        self.assertGreaterEqual(len(gold), 6)
        self.assertTrue(all(case["status"] == "ACTIVE" for case in gold))

    def test_clinical_draft_cases_are_not_gold_or_training_data(self):
        cases = load_jsonl(ROOT / "knowledge/evaluations/policy_baseline.jsonl")
        clinical_drafts = [case for case in cases if case["case_id"].startswith("CLINICAL_DRAFT_")]
        self.assertEqual(6, len(clinical_drafts))
        self.assertTrue(all(case["status"] == "DRAFT" for case in clinical_drafts))
        self.assertTrue(all(case["split"] == "DEV" for case in clinical_drafts))


if __name__ == "__main__":
    unittest.main()
