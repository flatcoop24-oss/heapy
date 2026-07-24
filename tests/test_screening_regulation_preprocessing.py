import csv
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts/preprocess_screening_regulation.py"
OUTPUT_DIR = ROOT / "storage/source_document/mohw_screening/normalized"

spec = importlib.util.spec_from_file_location("screening_preprocess", SCRIPT_PATH)
screening_preprocess = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(screening_preprocess)


class ScreeningRegulationPreprocessingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dataset_path = OUTPUT_DIR / screening_preprocess.DATASET_JSON
        cls.dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    def test_official_source_pdfs_are_unchanged_and_anchored(self):
        documents, errors = screening_preprocess.verify_documents()
        self.assertEqual([], errors)
        self.assertEqual(3, len(documents))

    def test_rule_graph_is_valid(self):
        self.assertEqual([], screening_preprocess.validate_rules())
        item_codes = {row["item_code"] for row in self.dataset["items"]}
        self.assertIn("SEX_FOR_CLINICAL_USE", item_codes)
        self.assertNotIn("SUBJECT_SEX", item_codes)
        for rule in self.dataset["rules"]:
            self.assertTrue(
                screening_preprocess.expression_fields(rule["expression"]) <= item_codes
            )

    def test_all_boundary_cases_match(self):
        for case in screening_preprocess.BOUNDARY_CASES:
            with self.subTest(case=case["id"]):
                result = screening_preprocess.evaluate_target(case["target"], case["values"])
                self.assertIsNotNone(result)
                self.assertEqual(case["expected"], result["result_code"])

    def test_phq9_item9_rule_has_priority_over_total_score(self):
        result = screening_preprocess.evaluate_target(
            "DEPRESSION_SCREEN", {"PHQ9_TOTAL": 8, "PHQ9_ITEM9": 1}
        )
        self.assertEqual("PHQ9_SEVERE_SUSPECTED", result["result_code"])

    def test_unknown_sex_for_clinical_use_does_not_guess_sex_scoped_result(self):
        result = screening_preprocess.evaluate_target(
            "ANEMIA",
            {"SEX_FOR_CLINICAL_USE": "UNKNOWN", "HEMOGLOBIN": 11.5},
        )
        self.assertIsNone(result)

    def test_multi_input_rules_are_not_flattened(self):
        composite_targets = {
            rule["target_condition"]
            for rule in self.dataset["rules"]
            if rule["rule_type"] == "COMPOSITE"
        }
        self.assertTrue(
            {
                "HYPERTENSION",
                "EARLY_PSYCHOSIS_SCREEN",
                "HEARING_WHISPER",
                "PULMONARY_BASIC",
                "PULMONARY_SIMPLE",
            }
            <= composite_targets
        )

    def test_quality_report_passes(self):
        report = json.loads(
            (OUTPUT_DIR / screening_preprocess.QUALITY_JSON).read_text(encoding="utf-8")
        )
        self.assertEqual("PASS", report["status"])
        self.assertTrue(all(report["checks"].values()))

    def test_csv_exports_match_json_grain(self):
        mappings = (
            (screening_preprocess.ITEMS_CSV, "items"),
            (screening_preprocess.RULES_CSV, "rules"),
            (screening_preprocess.ELIGIBILITY_CSV, "eligibility"),
            (screening_preprocess.LABS_MASTER_CSV, "lab_item_profiles"),
        )
        for filename, key in mappings:
            with self.subTest(filename=filename):
                with (OUTPUT_DIR / filename).open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                self.assertEqual(len(self.dataset[key]), len(rows))

    def test_labs_item_master_has_all_15_official_items(self):
        profiles = self.dataset["lab_item_profiles"]
        self.assertEqual(15, len(profiles))
        self.assertEqual(list(range(1, 16)), [row["display_order"] for row in profiles])
        self.assertEqual(
            {
                "HEMOGLOBIN",
                "FASTING_GLUCOSE",
                "TOTAL_CHOLESTEROL",
                "HDL_CHOLESTEROL",
                "TRIGLYCERIDES",
                "LDL_CHOLESTEROL",
                "AST",
                "ALT",
                "GAMMA_GTP",
                "SERUM_CREATININE",
                "EGFR",
                "URINE_PROTEIN",
                "HEPATITIS_B_SURFACE_ANTIGEN",
                "HEPATITIS_B_SURFACE_ANTIBODY",
                "HEPATITIS_C_ANTIBODY",
            },
            {row["item_code"] for row in profiles},
        )

    def test_labs_item_master_preserves_non_numeric_interpretation(self):
        profiles = {
            row["item_code"]: row for row in self.dataset["lab_item_profiles"]
        }
        self.assertTrue(
            all("sex_specific" not in profile for profile in profiles.values())
        )
        sex_scoped_items = set()
        for rule in self.dataset["rules"]:
            fields = screening_preprocess.expression_fields(rule["expression"])
            if "SEX_FOR_CLINICAL_USE" not in fields:
                continue
            sex_scoped_items.update(code for code in profiles if code in fields)
        self.assertEqual(
            {"HEMOGLOBIN", "GAMMA_GTP"},
            sex_scoped_items,
        )
        self.assertEqual(
            "SOURCE_REPORTED_COMPOSITE",
            profiles["HEPATITIS_B_SURFACE_ANTIGEN"]["interpretation_mode"],
        )
        self.assertEqual(
            "SOURCE_REPORTED_COMPOSITE",
            profiles["HEPATITIS_B_SURFACE_ANTIBODY"]["interpretation_mode"],
        )
        self.assertEqual(
            "SOURCE_REPORTED",
            profiles["HEPATITIS_C_ANTIBODY"]["interpretation_mode"],
        )
        self.assertEqual(
            "CONDITIONAL", profiles["LDL_CHOLESTEROL"]["derivation_mode"]
        )
        self.assertEqual("ALWAYS", profiles["EGFR"]["derivation_mode"])
        self.assertTrue(profiles["EGFR"]["derivation_requires_sex"])
        self.assertEqual("", profiles["SERUM_CREATININE"]["normal_b"])
        self.assertEqual("", profiles["EGFR"]["normal_b"])

    def test_labs_csv_json_columns_are_machine_readable(self):
        path = OUTPUT_DIR / screening_preprocess.LABS_MASTER_CSV
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            with self.subTest(item_code=row["item_code"]):
                self.assertIsInstance(json.loads(row["allowed_values"]), list)
                self.assertIsInstance(json.loads(row["eligibility"]), dict)
                self.assertIsInstance(json.loads(row["categories"]), list)
                self.assertIn(
                    row["classification_sex_specific"], {"True", "False"}
                )
                self.assertIn(row["eligibility_sex_specific"], {"True", "False"})
                self.assertIn(
                    row["requires_sex_for_clinical_use"], {"True", "False"}
                )
                self.assertTrue(row["source_locator"])

    def test_overall_and_oral_result_definitions_are_preserved(self):
        codes = {row["result_code"] for row in self.dataset["result_definitions"]}
        self.assertTrue(
            {
                "NORMAL_A",
                "NORMAL_B",
                "GENERAL_DISEASE_SUSPECTED",
                "CARDIOMETABOLIC_DISEASE_SUSPECTED",
                "KNOWN_DISEASE",
                "ORAL_GOOD",
                "ORAL_CAUTION",
                "ORAL_DISEASE_SUSPECTED",
                "ORAL_TREATMENT_REQUIRED",
            }
            <= codes
        )


if __name__ == "__main__":
    unittest.main()
