import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_screening_rag_serving",
    ROOT / "scripts/build_screening_rag_serving.py",
)
build_screening_rag_serving = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(build_screening_rag_serving)


class ScreeningRagServingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.authoring = build_screening_rag_serving.load_jsonl(
            build_screening_rag_serving.AUTHORING_PATH
        )
        cls.serving = build_screening_rag_serving.load_jsonl(
            build_screening_rag_serving.SERVING_PATH
        )
        cls.authoring_by_key = {
            chunk["canonical_key"]: chunk for chunk in cls.authoring
        }

    def test_serving_records_pass_validator(self):
        self.assertEqual(
            [],
            build_screening_rag_serving.validate_records(self.serving),
        )

    def test_serving_file_is_synchronized_with_authoring(self):
        expected = build_screening_rag_serving.build_records(self.authoring)
        self.assertEqual(expected, self.serving)
        self.assertEqual(
            build_screening_rag_serving.render_jsonl(expected),
            build_screening_rag_serving.SERVING_PATH.read_text(encoding="utf-8"),
        )

    def test_all_fifteen_approved_chunks_are_served(self):
        self.assertEqual(15, len(self.authoring))
        self.assertEqual(15, len(self.serving))
        self.assertEqual(
            set(self.authoring_by_key),
            {record["chunk_id"] for record in self.serving},
        )

    def test_embedding_text_uses_only_heading_content_and_keywords(self):
        for record in self.serving:
            authoring = self.authoring_by_key[record["chunk_id"]]
            expected_text = build_screening_rag_serving.build_embedding_text(authoring)
            self.assertEqual(expected_text, record["text"])
            self.assertEqual(
                hashlib.sha256(expected_text.encode("utf-8")).hexdigest(),
                record["text_sha256"],
            )

    def test_authoring_governance_fields_are_not_in_serving_payload(self):
        forbidden = {
            "section_type",
            "review_status",
            "status",
            "keywords",
            "heading",
            "content",
            "source_url",
            "source_locator",
            "locator_hint",
        }
        for record in self.serving:
            self.assertFalse(forbidden & record.keys())
            self.assertFalse(forbidden & record["metadata"].keys())

    def test_serving_payload_does_not_contain_urls_or_locator_language(self):
        for record in self.serving:
            serialized = json.dumps(record, ensure_ascii=False)
            self.assertNotIn("https://", serialized)
            self.assertNotIn("source_locator", serialized)
            self.assertNotIn("locator_hint", serialized)


if __name__ == "__main__":
    unittest.main()
