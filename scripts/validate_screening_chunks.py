#!/usr/bin/env python3
"""Validate the Data-owned health-screening chunk authoring source."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHUNK_PATH = ROOT / "knowledge/chunks/screening-labs-v1.jsonl"
EVIDENCE_PATH = ROOT / "knowledge/provenance/screening-labs-evidence-v1.jsonl"
ITEM_MASTER_PATH = (
    ROOT
    / "storage/source_document/mohw_screening/normalized"
    / "2026-01-07__MOHW-2026-6__labs-item-master.csv"
)

CHUNK_REQUIRED = {
    "canonical_key",
    "item_codes",
    "section_type",
    "domain",
    "heading",
    "content",
    "keywords",
    "safety_level",
    "evidence_ids",
    "review_status",
    "version",
    "status",
}
EVIDENCE_REQUIRED = {
    "evidence_id",
    "label",
    "source_url",
    "source_kind",
    "locator_hint",
    "locator_status",
    "review_status",
    "version",
    "status",
}
FORBIDDEN_CHUNK_FIELDS = {
    "route_scope",
    "intent",
    "sub_intent",
    "sub_intents",
    "embedding",
    "embedding_model",
    "vector",
    "token_count",
    "search_text",
    "content_hash",
    "source_document_id",
    "source_locator",
    "normal_a",
    "normal_b",
    "disease_suspected",
}
VALID_SECTION_TYPES = {"LAB_EXPLANATION", "TEST_EXPLANATION"}
VALID_DOMAINS = {
    "HEMATOLOGY",
    "GLUCOSE_METABOLISM",
    "LIPID",
    "LIVER",
    "KIDNEY",
    "INFECTIOUS_DISEASE",
}
VALID_SAFETY_LEVELS = {"LOW", "MODERATE", "HIGH"}
VALID_REVIEW_STATUSES = {
    "DRAFT",
    "SOURCE_VERIFIED",
    "CLINICALLY_APPROVED",
    "REJECTED",
}
VALID_STATUSES = {"DRAFT", "ACTIVE", "DEFERRED", "RETIRED", "REJECTED"}
RETRIEVABLE_REVIEW_STATUSES = {"SOURCE_VERIFIED", "CLINICALLY_APPROVED"}
IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
NUMERIC_RULE_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:~|–|—|-|이상|이하|미만|초과)"
)


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}:{line_number}: each line must be an object")
            continue
        records.append(value)
    return records, errors


def load_item_codes(path: Path = ITEM_MASTER_PATH) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [row["item_code"] for row in csv.DictReader(handle)]


def _validate_string_list(
    record_name: str,
    field_name: str,
    value: Any,
    minimum: int,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{record_name}: {field_name} must be an array"]
    if len(value) < minimum:
        errors.append(f"{record_name}: {field_name} must have at least {minimum} values")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{record_name}: {field_name} must contain non-empty strings")
    if len(value) != len(set(value)):
        errors.append(f"{record_name}: {field_name} must not contain duplicates")
    return errors


def validate(
    chunks: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
    item_codes: list[str],
) -> list[str]:
    errors: list[str] = []

    evidence_ids: list[str] = []
    for index, evidence in enumerate(evidence_records, start=1):
        name = evidence.get("evidence_id", f"evidence line {index}")
        missing = EVIDENCE_REQUIRED - evidence.keys()
        extra = evidence.keys() - EVIDENCE_REQUIRED
        if missing:
            errors.append(f"{name}: missing evidence fields {sorted(missing)}")
        if extra:
            errors.append(f"{name}: unexpected evidence fields {sorted(extra)}")
        evidence_id = evidence.get("evidence_id")
        if not isinstance(evidence_id, str) or not IDENTIFIER_RE.fullmatch(evidence_id):
            errors.append(f"{name}: invalid evidence_id")
        else:
            evidence_ids.append(evidence_id)
        source_url = evidence.get("source_url")
        if not isinstance(source_url, str) or not source_url.startswith("https://"):
            errors.append(f"{name}: source_url must use https")
        if evidence.get("locator_status") not in {
            "PENDING_STANDARDIZATION",
            "STANDARDIZED",
        }:
            errors.append(f"{name}: invalid locator_status")
        if evidence.get("review_status") != "SOURCE_VERIFIED":
            errors.append(f"{name}: active evidence must be SOURCE_VERIFIED")
        if evidence.get("status") != "ACTIVE":
            errors.append(f"{name}: v1 evidence registry only permits ACTIVE records")
        if not isinstance(evidence.get("version"), str) or not SEMVER_RE.fullmatch(
            evidence["version"]
        ):
            errors.append(f"{name}: version must be semantic version format")

    duplicate_evidence = [
        evidence_id
        for evidence_id, count in Counter(evidence_ids).items()
        if count > 1
    ]
    if duplicate_evidence:
        errors.append(f"duplicate evidence_ids: {sorted(duplicate_evidence)}")
    known_evidence_ids = set(evidence_ids)

    canonical_keys: list[str] = []
    covered_item_codes: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        name = chunk.get("canonical_key", f"chunk line {index}")
        missing = CHUNK_REQUIRED - chunk.keys()
        extra = chunk.keys() - CHUNK_REQUIRED
        if missing:
            errors.append(f"{name}: missing chunk fields {sorted(missing)}")
        if extra:
            errors.append(f"{name}: unexpected chunk fields {sorted(extra)}")
        forbidden = FORBIDDEN_CHUNK_FIELDS & chunk.keys()
        if forbidden:
            errors.append(f"{name}: downstream-owned fields are forbidden {sorted(forbidden)}")

        canonical_key = chunk.get("canonical_key")
        if not isinstance(canonical_key, str) or not IDENTIFIER_RE.fullmatch(canonical_key):
            errors.append(f"{name}: invalid canonical_key")
        else:
            canonical_keys.append(canonical_key)

        chunk_item_codes = chunk.get("item_codes")
        errors.extend(_validate_string_list(name, "item_codes", chunk_item_codes, 1))
        if isinstance(chunk_item_codes, list):
            covered_item_codes.extend(
                item_code for item_code in chunk_item_codes if isinstance(item_code, str)
            )
            invalid_item_codes = [
                item_code
                for item_code in chunk_item_codes
                if not isinstance(item_code, str)
                or not IDENTIFIER_RE.fullmatch(item_code)
            ]
            if invalid_item_codes:
                errors.append(f"{name}: invalid item_codes {invalid_item_codes}")
            if len(chunk_item_codes) != 1:
                errors.append(f"{name}: v1 overview chunk must map to exactly one item_code")
            elif canonical_key != chunk_item_codes[0]:
                errors.append(f"{name}: canonical_key must equal its v1 item_code")

        if chunk.get("section_type") not in VALID_SECTION_TYPES:
            errors.append(f"{name}: invalid section_type")
        if chunk.get("domain") not in VALID_DOMAINS:
            errors.append(f"{name}: invalid domain")
        if chunk.get("safety_level") not in VALID_SAFETY_LEVELS:
            errors.append(f"{name}: invalid safety_level")
        if chunk.get("review_status") not in VALID_REVIEW_STATUSES:
            errors.append(f"{name}: invalid review_status")
        if chunk.get("status") not in VALID_STATUSES:
            errors.append(f"{name}: invalid status")

        heading = chunk.get("heading")
        if not isinstance(heading, str) or len(heading.strip()) < 2:
            errors.append(f"{name}: heading is too short")
        content = chunk.get("content")
        if not isinstance(content, str) or len(content.strip()) < 80:
            errors.append(f"{name}: content must be at least 80 characters")
        elif NUMERIC_RULE_RE.search(content):
            errors.append(f"{name}: numeric classification rules belong in the RDB rule engine")

        errors.extend(_validate_string_list(name, "keywords", chunk.get("keywords"), 4))
        errors.extend(
            _validate_string_list(name, "evidence_ids", chunk.get("evidence_ids"), 1)
        )
        if isinstance(chunk.get("evidence_ids"), list):
            unresolved = sorted(set(chunk["evidence_ids"]) - known_evidence_ids)
            if unresolved:
                errors.append(f"{name}: unresolved evidence_ids {unresolved}")

        if not isinstance(chunk.get("version"), str) or not SEMVER_RE.fullmatch(
            chunk["version"]
        ):
            errors.append(f"{name}: version must be semantic version format")
        if (
            chunk.get("status") == "ACTIVE"
            and chunk.get("review_status") not in RETRIEVABLE_REVIEW_STATUSES
        ):
            errors.append(f"{name}: ACTIVE chunks must be source-verified or approved")
        if chunk.get("review_status") == "DRAFT" and chunk.get("status") != "DRAFT":
            errors.append(f"{name}: DRAFT review_status must remain DRAFT")

    duplicate_keys = [
        canonical_key
        for canonical_key, count in Counter(canonical_keys).items()
        if count > 1
    ]
    if duplicate_keys:
        errors.append(f"duplicate canonical_keys: {sorted(duplicate_keys)}")

    expected_items = set(item_codes)
    covered_items = set(covered_item_codes)
    missing_items = sorted(expected_items - covered_items)
    extra_items = sorted(covered_items - expected_items)
    duplicate_items = sorted(
        item_code
        for item_code, count in Counter(covered_item_codes).items()
        if count > 1
    )
    if missing_items:
        errors.append(f"item master codes missing from chunks: {missing_items}")
    if extra_items:
        errors.append(f"unknown item codes in chunks: {extra_items}")
    if duplicate_items:
        errors.append(f"item codes covered more than once: {duplicate_items}")
    if len(chunks) != len(item_codes):
        errors.append(
            f"chunk count {len(chunks)} must equal item master count {len(item_codes)}"
        )

    return errors


def main() -> int:
    chunks, chunk_load_errors = load_jsonl(CHUNK_PATH)
    evidence, evidence_load_errors = load_jsonl(EVIDENCE_PATH)
    errors = chunk_load_errors + evidence_load_errors
    errors.extend(validate(chunks, evidence, load_item_codes()))
    if errors:
        print("screening chunk validation failed")
        for error in errors:
            print(f"- {error}")
        return 1

    status_counts = Counter(chunk["status"] for chunk in chunks)
    print(
        "screening chunk validation passed: "
        f"{len(chunks)} chunks "
        f"({status_counts['ACTIVE']} active, {status_counts['DRAFT']} draft), "
        f"{len(evidence)} evidence records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
