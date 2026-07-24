import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/classify_user_screening.py"

spec = importlib.util.spec_from_file_location(
    "classify_user_screening",
    SCRIPT,
)
classify_user_screening = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(classify_user_screening)


class UserScreeningClassificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classifier = (
            classify_user_screening.UserScreeningClassifier.from_path()
        )

    def record(self, item_code, **overrides):
        value = {
            "record_id": f"TEST_{item_code}",
            "item_code": item_code,
            "screened_on": "2026-07-24",
            "sex_for_clinical_use": "MALE",
            "report_verification_status": "USER_CONFIRMED",
            "observation_verification_status": "USER_CONFIRMED",
            "extraction_confidence": 0.5,
        }
        value.update(overrides)
        return value

    def classify(self, item_code, **overrides):
        return self.classifier.classify(self.record(item_code, **overrides))

    def test_all_fifteen_lab_items_are_covered(self):
        self.assertEqual(15, len(self.classifier.profiles))
        self.assertEqual(
            set(self.classifier.profiles),
            set(self.classifier.items)
            & (
                set(classify_user_screening.ITEM_TARGETS)
                | {
                    "HEPATITIS_B_SURFACE_ANTIGEN",
                    "HEPATITIS_B_SURFACE_ANTIBODY",
                    "HEPATITIS_C_ANTIBODY",
                }
            ),
        )

    def test_outputs_follow_shared_schema(self):
        schema = json.loads(
            (
                ROOT
                / "knowledge/schemas/user-screening-classification.schema.json"
            ).read_text(encoding="utf-8")
        )
        records = (
            self.classify(
                "FASTING_GLUCOSE",
                value_numeric=99,
                unit="mg/dL",
            ),
            self.classify(
                "HEMOGLOBIN",
                value_numeric=13,
                unit="g/dL",
                sex_for_clinical_use="UNKNOWN",
            ),
            self.classify(
                "HEPATITIS_B_SURFACE_ANTIBODY",
                reported_interpretation_code="항체 있음",
            ),
        )
        for record in records:
            self.assertEqual(set(schema["required"]), set(record))
            self.assertFalse(set(record) - set(schema["properties"]))
            self.assertIn(
                record["classification_status"],
                schema["properties"]["classification_status"]["enum"],
            )
            self.assertIn(
                record["decision_state"],
                schema["properties"]["decision_state"]["enum"],
            )
            self.assertEqual(
                set(schema["properties"]["rule"]["required"]),
                set(record["rule"]),
            )

    def test_database_guard_layer_exposes_same_safety_contract(self):
        sql = (
            ROOT
            / "database/migrations/075_user_screening_classification.sql"
        ).read_text(encoding="utf-8")
        for marker in (
            "classify_user_screening_observation",
            "user_screening_record_classification",
            "reported_interpretation_code",
            "UNVERIFIED_RESULT",
            "LOW_EXTRACTION_CONFIDENCE",
            "SEX_FOR_CLINICAL_USE_REQUIRED",
            "UNIT_MISMATCH",
            "SOURCE_COMPUTED_MISMATCH",
            "OUTSIDE_DEFINED_OFFICIAL_RANGE",
        ):
            self.assertIn(marker, sql)

    def test_database_seed_uses_canonical_urine_protein_codes(self):
        sql = (
            ROOT / "database/seeds/020_screening_dictionary.sql"
        ).read_text(encoding="utf-8")
        for code in (
            "NEGATIVE",
            "TRACE",
            "POSITIVE_1",
            "POSITIVE_2",
            "POSITIVE_3",
            "POSITIVE_4",
        ):
            self.assertIn(
                f"'URINE_PROTEIN', 'ANY'",
                sql,
            )
            self.assertIn(f"'{code}'", sql)

    def test_existing_urine_protein_rules_have_forward_migration(self):
        sql = (
            ROOT
            / "database/migrations/076_normalize_urine_protein_rules.sql"
        ).read_text(encoding="utf-8")
        expected_mapping = {
            "-": "NEGATIVE",
            "±": "TRACE",
            "+1": "POSITIVE_1",
            "+2": "POSITIVE_2",
            "+3": "POSITIVE_3",
            "+4": "POSITIVE_4",
        }
        for legacy, canonical in expected_mapping.items():
            self.assertIn(f"WHEN '{legacy}' THEN '{canonical}'", sql)
        self.assertIn("IS NOT DISTINCT FROM", sql)

    def test_postgres_integration_fixture_covers_all_items_and_guards(self):
        sql = (
            ROOT
            / "tests/sql/user_screening_classification_integration.sql"
        ).read_text(encoding="utf-8")
        for item_code in self.classifier.profiles:
            self.assertIn(f"'{item_code}'", sql)
        for reason_code in (
            "UNIT_MISMATCH",
            "SOURCE_COMPUTED_MISMATCH",
            "OUTSIDE_DEFINED_OFFICIAL_RANGE",
            "SEX_FOR_CLINICAL_USE_REQUIRED",
            "LOW_EXTRACTION_CONFIDENCE",
        ):
            self.assertIn(reason_code, sql)

    def test_glucose_boundaries_follow_official_rule(self):
        cases = (
            (99, "NORMAL_A"),
            (100, "NORMAL_B"),
            (125, "NORMAL_B"),
            (126, "DISEASE_SUSPECTED"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                result = self.classify(
                    "FASTING_GLUCOSE",
                    value_numeric=value,
                    unit="mg/dL",
                )
                self.assertEqual(expected, result["classification_status"])
                self.assertEqual("CLASSIFIED", result["decision_state"])

    def test_normal_a_is_the_only_true_normal_flag(self):
        normal = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=99,
            unit="mg/dL",
        )
        borderline = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=100,
            unit="mg/dL",
        )
        suspected = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=126,
            unit="mg/dL",
        )
        self.assertIs(normal["is_normal_a"], True)
        self.assertIs(borderline["is_normal_a"], False)
        self.assertIs(suspected["is_normal_a"], False)

    def test_user_confirmation_overrides_low_ocr_confidence(self):
        result = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=99,
            unit="mg/dL",
            observation_verification_status="USER_CONFIRMED",
            extraction_confidence=0.2,
        )
        self.assertEqual("NORMAL_A", result["classification_status"])

    def test_unconfirmed_low_confidence_is_not_classified(self):
        result = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=99,
            unit="mg/dL",
            report_verification_status="AUTO_VALIDATED",
            observation_verification_status="AUTO_VALIDATED",
            extraction_confidence=0.94,
        )
        self.assertEqual("UNCLASSIFIED", result["classification_status"])
        self.assertEqual("LOW_EXTRACTION_CONFIDENCE", result["reason_code"])

    def test_unverified_result_is_not_classified(self):
        result = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=99,
            unit="mg/dL",
            observation_verification_status="UNVERIFIED",
        )
        self.assertEqual("UNVERIFIED_RESULT", result["reason_code"])
        self.assertTrue(result["requires_review"])

    def test_sex_scoped_item_requires_clinical_sex(self):
        result = self.classify(
            "HEMOGLOBIN",
            value_numeric=13,
            unit="g/dL",
            sex_for_clinical_use="UNKNOWN",
        )
        self.assertEqual(
            "SEX_FOR_CLINICAL_USE_REQUIRED",
            result["reason_code"],
        )

    def test_hemoglobin_does_not_infer_undefined_high_range(self):
        result = self.classify(
            "HEMOGLOBIN",
            value_numeric=17,
            unit="g/dL",
            sex_for_clinical_use="MALE",
        )
        self.assertEqual(
            "OUTSIDE_DEFINED_OFFICIAL_RANGE",
            result["reason_code"],
        )

    def test_gamma_gtp_does_not_infer_undefined_low_range(self):
        result = self.classify(
            "GAMMA_GTP",
            value_numeric=7,
            unit="U/L",
            sex_for_clinical_use="FEMALE",
        )
        self.assertEqual(
            "OUTSIDE_DEFINED_OFFICIAL_RANGE",
            result["reason_code"],
        )

    def test_enzyme_unit_alias_accepts_iu_per_litre(self):
        result = self.classify(
            "AST",
            value_numeric=40,
            unit="IU/L",
        )
        self.assertEqual("NORMAL_A", result["classification_status"])

    def test_unit_mismatch_blocks_numeric_classification(self):
        result = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=5.5,
            unit="mmol/L",
        )
        self.assertEqual("UNIT_MISMATCH", result["reason_code"])

    def test_urine_protein_symbols_are_normalized(self):
        cases = (
            ("음성", "NORMAL_A"),
            ("-", "NORMAL_A"),
            ("±", "NORMAL_B"),
            ("1+", "DISEASE_SUSPECTED"),
            ("+4", "DISEASE_SUSPECTED"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                result = self.classify(
                    "URINE_PROTEIN",
                    value_text=value,
                )
                self.assertEqual(expected, result["classification_status"])

    def test_hepatitis_c_uses_source_reported_result(self):
        negative = self.classify(
            "HEPATITIS_C_ANTIBODY",
            value_text="항체 없음",
        )
        positive = self.classify(
            "HEPATITIS_C_ANTIBODY",
            reported_interpretation_code="항체 있음",
        )
        self.assertEqual("NORMAL_A", negative["classification_status"])
        self.assertEqual(
            "DISEASE_SUSPECTED",
            positive["classification_status"],
        )
        self.assertEqual("SOURCE_REPORTED", negative["basis"])

    def test_hepatitis_b_antigen_value_is_not_independently_normalized(self):
        result = self.classify(
            "HEPATITIS_B_SURFACE_ANTIGEN",
            value_text="음성",
        )
        self.assertEqual("SOURCE_RESULT_REQUIRED", result["reason_code"])

    def test_hepatitis_b_composite_result_is_preserved(self):
        immune = self.classify(
            "HEPATITIS_B_SURFACE_ANTIBODY",
            reported_interpretation_code="항체 있음",
        )
        suspected = self.classify(
            "HEPATITIS_B_SURFACE_ANTIGEN",
            reported_interpretation_code="B형간염 보유자 의심",
        )
        self.assertEqual("SOURCE_REPORTED", immune["classification_status"])
        self.assertIsNone(immune["is_normal_a"])
        self.assertEqual(
            "DISEASE_SUSPECTED",
            suspected["classification_status"],
        )

    def test_historical_record_requires_historical_rule_set(self):
        result = self.classify(
            "FASTING_GLUCOSE",
            screened_on="2025-12-31",
            value_numeric=99,
            unit="mg/dL",
        )
        self.assertEqual(
            "HISTORICAL_RULE_NOT_AVAILABLE",
            result["reason_code"],
        )

    def test_source_and_computed_mismatch_requires_review(self):
        result = self.classify(
            "FASTING_GLUCOSE",
            value_numeric=99,
            unit="mg/dL",
            reported_interpretation_code="NORMAL_B",
        )
        self.assertEqual("UNCLASSIFIED", result["classification_status"])
        self.assertEqual("SOURCE_COMPUTED_MISMATCH", result["reason_code"])
        self.assertTrue(result["source_computed_mismatch"])


if __name__ == "__main__":
    unittest.main()
