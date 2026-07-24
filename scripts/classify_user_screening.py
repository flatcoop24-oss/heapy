#!/usr/bin/env python3
"""Classify verified user screening records with the official RDB rule dataset.

This module is intentionally separate from RAG. It consumes the normalized
Ministry of Health and Welfare screening rules and returns a deterministic
screening classification. It is not a diagnosis engine.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = (
    ROOT
    / "storage/source_document/mohw_screening/normalized"
    / "2026-01-07__MOHW-2026-6__screening-regulation.json"
)

ACCEPTED_VERIFICATION_STATUSES = {"AUTO_VALIDATED", "USER_CONFIRMED"}
GENERIC_REPORTED_STATUSES = {
    "NORMAL_A",
    "NORMAL_B",
    "DISEASE_SUSPECTED",
}

ITEM_TARGETS = {
    "HEMOGLOBIN": "ANEMIA",
    "FASTING_GLUCOSE": "DIABETES",
    "TOTAL_CHOLESTEROL": "DYSLIPIDEMIA_TOTAL",
    "HDL_CHOLESTEROL": "DYSLIPIDEMIA_HDL",
    "TRIGLYCERIDES": "DYSLIPIDEMIA_TG",
    "LDL_CHOLESTEROL": "DYSLIPIDEMIA_LDL",
    "AST": "LIVER_AST",
    "ALT": "LIVER_ALT",
    "GAMMA_GTP": "LIVER_GGT",
    "SERUM_CREATININE": "KIDNEY_CREATININE",
    "EGFR": "KIDNEY_EGFR",
    "URINE_PROTEIN": "KIDNEY_URINE_PROTEIN",
}

NORMALITY = {
    "NORMAL_A": "NORMAL",
    "NORMAL_B": "BORDERLINE",
    "DISEASE_SUSPECTED": "SUSPECTED",
    "SOURCE_REPORTED": "SOURCE_REPORTED",
    "UNCLASSIFIED": "UNCLASSIFIED",
}

UNIT_ALIASES = {
    "g/dl": "g/dl",
    "mg/dl": "mg/dl",
    "u/l": "u/l",
    "iu/l": "u/l",
    "ml/min/1.73m2": "ml/min/1.73m2",
    "ml/min/1.73㎡": "ml/min/1.73m2",
}

URINE_PROTEIN_ALIASES = {
    "negative": "NEGATIVE",
    "neg": "NEGATIVE",
    "음성": "NEGATIVE",
    "-": "NEGATIVE",
    "trace": "TRACE",
    "약양성": "TRACE",
    "±": "TRACE",
    "+-": "TRACE",
    "positive1": "POSITIVE_1",
    "1+": "POSITIVE_1",
    "+1": "POSITIVE_1",
    "+": "POSITIVE_1",
    "양성": "POSITIVE_1",
    "positive2": "POSITIVE_2",
    "2+": "POSITIVE_2",
    "+2": "POSITIVE_2",
    "positive3": "POSITIVE_3",
    "3+": "POSITIVE_3",
    "+3": "POSITIVE_3",
    "positive4": "POSITIVE_4",
    "4+": "POSITIVE_4",
    "+4": "POSITIVE_4",
}

HEPATITIS_C_ALIASES = {
    "negative": "HEPATITIS_C_ANTIBODY_ABSENT",
    "neg": "HEPATITIS_C_ANTIBODY_ABSENT",
    "음성": "HEPATITIS_C_ANTIBODY_ABSENT",
    "항체없음": "HEPATITIS_C_ANTIBODY_ABSENT",
    "없음": "HEPATITIS_C_ANTIBODY_ABSENT",
    "hepatitiscantibodyabsent": "HEPATITIS_C_ANTIBODY_ABSENT",
    "positive": "HEPATITIS_C_ANTIBODY_PRESENT",
    "pos": "HEPATITIS_C_ANTIBODY_PRESENT",
    "양성": "HEPATITIS_C_ANTIBODY_PRESENT",
    "항체있음": "HEPATITIS_C_ANTIBODY_PRESENT",
    "있음": "HEPATITIS_C_ANTIBODY_PRESENT",
    "hepatitiscantibodypresent": "HEPATITIS_C_ANTIBODY_PRESENT",
    "indeterminate": "INDETERMINATE",
    "판정보류": "INDETERMINATE",
}

HEPATITIS_B_ALIASES = {
    "hepatitisbcarriersuspected": "HEPATITIS_B_CARRIER_SUSPECTED",
    "b형간염보유자의심": "HEPATITIS_B_CARRIER_SUSPECTED",
    "hepatitisbantibodypresent": "HEPATITIS_B_ANTIBODY_PRESENT",
    "항체있음": "HEPATITIS_B_ANTIBODY_PRESENT",
    "hepatitisbantibodyabsent": "HEPATITIS_B_ANTIBODY_ABSENT",
    "항체없음": "HEPATITIS_B_ANTIBODY_ABSENT",
    "hepatitisbpending": "HEPATITIS_B_PENDING",
    "판정보류": "HEPATITIS_B_PENDING",
}


def normalize_token(value: Any) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).strip().lower()
    return re.sub(r"[\s_()\[\]{}·.,:/-]+", "", normalized)


def normalize_unit(value: Any) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(value)).strip().lower()
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.replace("㎎", "mg").replace("㎗", "dl")
    normalized = normalized.replace("㎡", "m2")
    return UNIT_ALIASES.get(normalized, normalized)


def normalize_reported_code(item_code: str, value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().upper()
    if raw in GENERIC_REPORTED_STATUSES:
        return raw
    token = normalize_token(value)
    if item_code == "HEPATITIS_C_ANTIBODY":
        return HEPATITIS_C_ALIASES.get(token)
    if item_code in {
        "HEPATITIS_B_SURFACE_ANTIGEN",
        "HEPATITIS_B_SURFACE_ANTIBODY",
    }:
        return HEPATITIS_B_ALIASES.get(token)
    return raw if re.fullmatch(r"[A-Z][A-Z0-9_]*", raw) else None


def normalize_code_value(item_code: str, value: Any) -> str | None:
    if value is None:
        return None
    if item_code == "URINE_PROTEIN":
        raw_display = unicodedata.normalize("NFKC", str(value)).strip()
        raw = raw_display.upper()
        if raw in {
            "NEGATIVE",
            "TRACE",
            "POSITIVE_1",
            "POSITIVE_2",
            "POSITIVE_3",
            "POSITIVE_4",
        }:
            return raw
        if raw_display in {"-", "±", "+-", "+", "1+", "+1", "2+", "+2", "3+", "+3", "4+", "+4"}:
            return URINE_PROTEIN_ALIASES[raw_display]
        return URINE_PROTEIN_ALIASES.get(normalize_token(value))
    return str(value).strip().upper()


def expression_fields(expression: dict[str, Any]) -> set[str]:
    if "field" in expression:
        return {expression["field"]}
    fields: set[str] = set()
    for key in ("all", "any"):
        for child in expression.get(key, []):
            fields.update(expression_fields(child))
    if "not" in expression:
        fields.update(expression_fields(expression["not"]))
    return fields


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise InvalidOperation
    return Decimal(str(value))


def evaluate_expression(
    expression: dict[str, Any],
    values: dict[str, Any],
) -> bool:
    if "all" in expression:
        return all(evaluate_expression(child, values) for child in expression["all"])
    if "any" in expression:
        return any(evaluate_expression(child, values) for child in expression["any"])
    if "not" in expression:
        return not evaluate_expression(expression["not"], values)

    field = expression["field"]
    if field not in values or values[field] is None:
        return False
    actual = values[field]
    expected = expression["value"]
    op = expression["op"]

    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected

    try:
        left = _decimal(actual)
        right = _decimal(expected)
    except (InvalidOperation, TypeError, ValueError):
        return False
    return {
        "lt": left < right,
        "lte": left <= right,
        "gt": left > right,
        "gte": left >= right,
    }[op]


class UserScreeningClassifier:
    def __init__(self, dataset: dict[str, Any]):
        self.dataset = dataset
        self.effective_from = date.fromisoformat(
            dataset["regulation"]["effective_from"]
        )
        self.rule_version = dataset["regulation"]["notice"]
        self.items = {row["item_code"]: row for row in dataset["items"]}
        self.profiles = {
            row["item_code"]: row for row in dataset["lab_item_profiles"]
        }
        self.rules_by_target: dict[str, list[dict[str, Any]]] = {}
        for rule in dataset["rules"]:
            self.rules_by_target.setdefault(rule["target_condition"], []).append(rule)

    @classmethod
    def from_path(
        cls,
        path: Path = DEFAULT_DATASET_PATH,
    ) -> "UserScreeningClassifier":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def _result(
        self,
        record: dict[str, Any],
        *,
        classification_status: str,
        decision_state: str,
        reason_code: str,
        basis: str,
        rule: dict[str, Any] | None = None,
        normalized_value: Any = None,
        reported_code: str | None = None,
        source_computed_mismatch: bool = False,
    ) -> dict[str, Any]:
        is_normal_a: bool | None
        if classification_status == "NORMAL_A":
            is_normal_a = True
        elif classification_status in {"NORMAL_B", "DISEASE_SUSPECTED"}:
            is_normal_a = False
        else:
            is_normal_a = None
        return {
            "record_id": record.get("record_id"),
            "item_code": record.get("item_code"),
            "classification_status": classification_status,
            "normality": NORMALITY[classification_status],
            "is_normal_a": is_normal_a,
            "decision_state": decision_state,
            "requires_review": decision_state == "REVIEW_REQUIRED",
            "reason_code": reason_code,
            "basis": basis,
            "normalized_value": normalized_value,
            "reported_interpretation_code": reported_code,
            "source_computed_mismatch": source_computed_mismatch,
            "rule": {
                "rule_id": rule["rule_id"],
                "rule_version": self.rule_version,
                "source_document_code": rule["source_document_code"],
                "source_locator": rule["source_locator"],
            }
            if rule
            else {
                "rule_id": None,
                "rule_version": self.rule_version,
                "source_document_code": None,
                "source_locator": None,
            },
            "disclaimer": "국가건강검진 결과 분류이며 의료 진단이나 처방이 아닙니다.",
        }

    def _unclassified(
        self,
        record: dict[str, Any],
        reason_code: str,
        *,
        normalized_value: Any = None,
        reported_code: str | None = None,
    ) -> dict[str, Any]:
        return self._result(
            record,
            classification_status="UNCLASSIFIED",
            decision_state="REVIEW_REQUIRED",
            reason_code=reason_code,
            basis="NONE",
            normalized_value=normalized_value,
            reported_code=reported_code,
        )

    def _classify_source_reported(
        self,
        record: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        item_code = record["item_code"]
        reported_code = normalize_reported_code(
            item_code,
            record.get("reported_interpretation_code")
            or record.get("value_text"),
        )
        if not reported_code:
            return self._unclassified(record, "SOURCE_RESULT_REQUIRED")

        if profile["interpretation_mode"] == "SOURCE_REPORTED_COMPOSITE":
            if reported_code == "HEPATITIS_B_CARRIER_SUSPECTED":
                return self._result(
                    record,
                    classification_status="DISEASE_SUSPECTED",
                    decision_state="CLASSIFIED",
                    reason_code="SOURCE_COMPOSITE_SUSPECTED",
                    basis="SOURCE_REPORTED",
                    reported_code=reported_code,
                )
            if reported_code in {
                "HEPATITIS_B_ANTIBODY_PRESENT",
                "HEPATITIS_B_ANTIBODY_ABSENT",
            }:
                return self._result(
                    record,
                    classification_status="SOURCE_REPORTED",
                    decision_state="SOURCE_RECORDED",
                    reason_code="SOURCE_COMPOSITE_RECORDED",
                    basis="SOURCE_REPORTED",
                    reported_code=reported_code,
                )
            return self._unclassified(
                record,
                "SOURCE_COMPOSITE_PENDING",
                reported_code=reported_code,
            )

        if item_code == "HEPATITIS_C_ANTIBODY":
            mapped = {
                "HEPATITIS_C_ANTIBODY_ABSENT": "NORMAL_A",
                "HEPATITIS_C_ANTIBODY_PRESENT": "DISEASE_SUSPECTED",
            }.get(reported_code)
            if not mapped:
                return self._unclassified(
                    record,
                    "SOURCE_RESULT_INDETERMINATE",
                    reported_code=reported_code,
                )
            return self._result(
                record,
                classification_status=mapped,
                decision_state="CLASSIFIED",
                reason_code="SOURCE_RESULT_CLASSIFIED",
                basis="SOURCE_REPORTED",
                reported_code=reported_code,
            )

        return self._unclassified(
            record,
            "UNSUPPORTED_SOURCE_REPORTED_ITEM",
            reported_code=reported_code,
        )

    def classify(self, record: dict[str, Any]) -> dict[str, Any]:
        item_code = str(record.get("item_code") or "").upper()
        record = {**record, "item_code": item_code or None}
        item = self.items.get(item_code)
        profile = self.profiles.get(item_code)
        if not item or not profile:
            return self._unclassified(record, "ITEM_UNMAPPED")

        report_verification = record.get(
            "report_verification_status",
            record.get("verification_status"),
        )
        observation_verification = record.get(
            "observation_verification_status",
            record.get("verification_status"),
        )
        if (
            report_verification not in ACCEPTED_VERIFICATION_STATUSES
            or observation_verification not in ACCEPTED_VERIFICATION_STATUSES
        ):
            return self._unclassified(record, "UNVERIFIED_RESULT")

        confidence = record.get("extraction_confidence")
        if (
            observation_verification != "USER_CONFIRMED"
            and confidence is not None
            and float(confidence) < 0.95
        ):
            return self._unclassified(record, "LOW_EXTRACTION_CONFIDENCE")

        try:
            screened_on = date.fromisoformat(str(record["screened_on"]))
        except (KeyError, TypeError, ValueError):
            return self._unclassified(record, "SCREENING_DATE_REQUIRED")
        if screened_on < self.effective_from:
            return self._unclassified(record, "HISTORICAL_RULE_NOT_AVAILABLE")

        if profile["interpretation_mode"] != "RULE_ENGINE":
            return self._classify_source_reported(record, profile)

        target = ITEM_TARGETS.get(item_code)
        if not target:
            return self._unclassified(record, "RULE_TARGET_NOT_CONFIGURED")
        rules = self.rules_by_target.get(target, [])
        if not rules:
            return self._unclassified(record, "RULE_NOT_AVAILABLE")

        requires_sex = any(
            "SEX_FOR_CLINICAL_USE" in expression_fields(rule["expression"])
            for rule in rules
        )
        sex = str(record.get("sex_for_clinical_use") or "UNKNOWN").upper()
        if requires_sex and sex not in {"MALE", "FEMALE"}:
            return self._unclassified(record, "SEX_FOR_CLINICAL_USE_REQUIRED")

        values: dict[str, Any] = {}
        normalized_value: Any
        if item["value_type"] == "NUMERIC":
            if record.get("value_numeric") is None:
                return self._unclassified(record, "NUMERIC_VALUE_REQUIRED")
            try:
                normalized_value = _decimal(record["value_numeric"])
            except (InvalidOperation, TypeError, ValueError):
                return self._unclassified(record, "INVALID_NUMERIC_VALUE")
            canonical_unit = normalize_unit(item.get("canonical_unit"))
            supplied_unit = normalize_unit(
                record.get("normalized_unit")
                or record.get("unit")
                or record.get("raw_unit")
            )
            if canonical_unit and supplied_unit is None:
                return self._unclassified(record, "UNIT_REQUIRED")
            if canonical_unit != supplied_unit:
                return self._unclassified(record, "UNIT_MISMATCH")
            values[item_code] = normalized_value
        else:
            normalized_value = normalize_code_value(
                item_code,
                record.get("value_text"),
            )
            if normalized_value is None:
                return self._unclassified(record, "CODE_VALUE_UNRECOGNIZED")
            if normalized_value not in item.get("allowed_values", []):
                return self._unclassified(
                    record,
                    "CODE_VALUE_NOT_ALLOWED",
                    normalized_value=normalized_value,
                )
            values[item_code] = normalized_value

        if requires_sex:
            values["SEX_FOR_CLINICAL_USE"] = sex

        matches = [
            rule
            for rule in rules
            if evaluate_expression(rule["expression"], values)
        ]
        if not matches:
            return self._unclassified(
                record,
                "OUTSIDE_DEFINED_OFFICIAL_RANGE",
                normalized_value=str(normalized_value),
            )
        rule = max(
            matches,
            key=lambda row: (row["priority"], row["severity_rank"]),
        )
        computed_status = rule["normalized_status"]
        reported_code = normalize_reported_code(
            item_code,
            record.get("reported_interpretation_code"),
        )
        mismatch = (
            reported_code in GENERIC_REPORTED_STATUSES
            and reported_code != computed_status
        )
        if mismatch:
            return self._result(
                record,
                classification_status="UNCLASSIFIED",
                decision_state="REVIEW_REQUIRED",
                reason_code="SOURCE_COMPUTED_MISMATCH",
                basis="OFFICIAL_RULE",
                rule=rule,
                normalized_value=str(normalized_value),
                reported_code=reported_code,
                source_computed_mismatch=True,
            )

        return self._result(
            record,
            classification_status=computed_status,
            decision_state="CLASSIFIED",
            reason_code="OFFICIAL_RULE_MATCH",
            basis="OFFICIAL_RULE",
            rule=rule,
            normalized_value=str(normalized_value),
            reported_code=reported_code,
        )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def render_jsonl(records: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            for record in records
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="User record JSONL")
    parser.add_argument("--output", type=Path, required=True, help="Classified JSONL")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    args = parser.parse_args()

    classifier = UserScreeningClassifier.from_path(args.dataset)
    results = [classifier.classify(record) for record in load_jsonl(args.input)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_jsonl(results), encoding="utf-8")
    classified = sum(
        result["decision_state"] == "CLASSIFIED" for result in results
    )
    review = sum(result["requires_review"] for result in results)
    print(
        f"classified user screening records: "
        f"input={len(results)}, classified={classified}, review_required={review}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
