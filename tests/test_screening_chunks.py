import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "validate_screening_chunks",
    ROOT / "scripts/validate_screening_chunks.py",
)
validate_screening_chunks = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(validate_screening_chunks)


def load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class ScreeningChunkDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = load_jsonl(validate_screening_chunks.CHUNK_PATH)
        cls.evidence = load_jsonl(validate_screening_chunks.EVIDENCE_PATH)
        cls.item_codes = validate_screening_chunks.load_item_codes()
        cls.by_key = {chunk["canonical_key"]: chunk for chunk in cls.chunks}

    def test_authoring_source_passes_validator(self):
        self.assertEqual(
            [],
            validate_screening_chunks.validate(
                self.chunks,
                self.evidence,
                self.item_codes,
            ),
        )

    def test_every_labs_master_item_has_one_overview_chunk(self):
        self.assertEqual(15, len(self.chunks))
        self.assertEqual(set(self.item_codes), set(self.by_key))
        for item_code, chunk in self.by_key.items():
            self.assertEqual([item_code], chunk["item_codes"])

    def test_verified_core_content_matches_existing_corpus(self):
        corpus = json.loads(
            (ROOT / "vdb/corpus/screening_core_v1.json").read_text(encoding="utf-8")
        )
        existing = {chunk["canonical_key"]: chunk for chunk in corpus["chunks"]}
        fields = [
            "section_type",
            "domain",
            "heading",
            "content",
            "keywords",
            "safety_level",
            "review_status",
        ]
        verified_chunks = [
            self.by_key[key]
            for key in self.by_key.keys() & existing.keys()
            if self.by_key[key]["review_status"] == "SOURCE_VERIFIED"
        ]
        self.assertEqual(12, len(verified_chunks))
        for chunk in verified_chunks:
            for field in fields:
                self.assertEqual(
                    existing[chunk["canonical_key"]][field],
                    chunk[field],
                    f"{chunk['canonical_key']} diverged on {field}",
                )

    def test_hepatitis_splits_are_source_verified_not_clinically_approved(self):
        hepatitis_keys = {
            "HEPATITIS_B_SURFACE_ANTIGEN",
            "HEPATITIS_B_SURFACE_ANTIBODY",
            "HEPATITIS_C_ANTIBODY",
        }
        actual_drafts = {
            chunk["canonical_key"]
            for chunk in self.chunks
            if chunk["status"] == "DRAFT"
        }
        self.assertEqual(set(), actual_drafts)
        for key in hepatitis_keys:
            self.assertEqual("SOURCE_VERIFIED", self.by_key[key]["review_status"])
            self.assertEqual("ACTIVE", self.by_key[key]["status"])
            self.assertEqual("1.0.1", self.by_key[key]["version"])
            self.assertNotEqual(
                "CLINICALLY_APPROVED",
                self.by_key[key]["review_status"],
            )

    def test_data_source_excludes_downstream_and_locator_fields(self):
        for chunk in self.chunks:
            self.assertFalse(
                validate_screening_chunks.FORBIDDEN_CHUNK_FIELDS & chunk.keys()
            )

    def test_numeric_classification_rules_are_not_in_chunk_content(self):
        for chunk in self.chunks:
            self.assertIsNone(
                validate_screening_chunks.NUMERIC_RULE_RE.search(chunk["content"]),
                chunk["canonical_key"],
            )

    def test_every_evidence_reference_resolves(self):
        evidence_ids = {record["evidence_id"] for record in self.evidence}
        for chunk in self.chunks:
            self.assertTrue(set(chunk["evidence_ids"]) <= evidence_ids)


if __name__ == "__main__":
    unittest.main()
