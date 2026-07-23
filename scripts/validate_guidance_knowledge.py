#!/usr/bin/env python3
"""Validate Health Guidance JSONL sources, evidence, policies and evaluation links."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = ROOT / "knowledge"

SOURCE_FILE = KNOWLEDGE_ROOT / "sources/source_documents.jsonl"
EVIDENCE_DIR = KNOWLEDGE_ROOT / "evidence"
POLICY_DIR = KNOWLEDGE_ROOT / "policies"
TEMPLATE_FILE = KNOWLEDGE_ROOT / "templates/response_templates.jsonl"
EVALUATION_DIR = KNOWLEDGE_ROOT / "evaluations"
CAPABILITY_FILE = KNOWLEDGE_ROOT / "capabilities/clinical_capabilities.jsonl"
REVIEW_FILE = KNOWLEDGE_ROOT / "reviews/clinical_reviews.jsonl"
SCHEMA_DIR = KNOWLEDGE_ROOT / "schemas"

ALLOWED_ACTIONS = {
    "ANSWER_GENERAL",
    "ASK_CONTEXT",
    "DISPLAY_RECORDED_DATA",
    "EXPLAIN_OFFICIAL_INFORMATION",
    "PROVIDE_CLINICAL_ASSESSMENT",
    "PROVIDE_TREATMENT_GUIDANCE",
    "PROVIDE_CONDITION_SPECIFIC_PLAN",
    "PROVIDE_MEDICATION_GUIDANCE",
    "CLINICAL_REVIEW_REQUIRED",
    "INSUFFICIENT_EVIDENCE",
    "SAFETY_ESCALATION",
}
ALLOWED_EMBEDDING_POLICIES = {
    "ALLOW_NORMALIZED_SUMMARY",
    "ALLOW_EXACT_API_FIELD_ON_DEMAND",
    "ALLOW_CLINICALLY_APPROVED_DERIVATIVE",
}
RESTRICTIVE_ACTIONS = {
    "CLINICAL_REVIEW_REQUIRED",
    "INSUFFICIENT_EVIDENCE",
    "SAFETY_ESCALATION",
}


@dataclass(frozen=True)
class Record:
    path: Path
    line_number: int
    value: dict[str, Any]

    @property
    def label(self) -> str:
        return f"{self.path.relative_to(ROOT)}:{self.line_number}"


def load_jsonl(path: Path) -> tuple[list[Record], list[str]]:
    records: list[Record] = []
    errors: list[str] = []
    if not path.exists():
        return records, [f"missing JSONL file: {path.relative_to(ROOT)}"]

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.relative_to(ROOT)}:{line_number}: record must be an object")
            continue
        records.append(Record(path, line_number, value))
    return records, errors


def load_directory(path: Path) -> tuple[list[Record], list[str]]:
    if not path.exists():
        return [], [f"missing directory: {path.relative_to(ROOT)}"]
    records: list[Record] = []
    errors: list[str] = []
    for jsonl_path in sorted(path.glob("*.jsonl")):
        loaded, load_errors = load_jsonl(jsonl_path)
        records.extend(loaded)
        errors.extend(load_errors)
    if not records:
        errors.append(f"no JSONL records found in {path.relative_to(ROOT)}")
    return records, errors


def require(record: Record, fields: Iterable[str], errors: list[str]) -> None:
    for field in fields:
        if field not in record.value:
            errors.append(f"{record.label}: missing required field {field}")


def index_unique(
    records: list[Record], key: str, kind: str, errors: list[str]
) -> dict[str, Record]:
    indexed: dict[str, Record] = {}
    for record in records:
        value = record.value.get(key)
        if not isinstance(value, str) or not value:
            errors.append(f"{record.label}: {key} must be a non-empty string")
            continue
        if value in indexed:
            errors.append(
                f"{record.label}: duplicate {kind} {value}; first seen at {indexed[value].label}"
            )
            continue
        indexed[value] = record
    return indexed


def validate() -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []

    for schema_path in sorted(SCHEMA_DIR.glob("*.json")):
        try:
            json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{schema_path.relative_to(ROOT)}: invalid JSON schema: {exc}")

    sources, source_errors = load_jsonl(SOURCE_FILE)
    evidence, evidence_errors = load_directory(EVIDENCE_DIR)
    policies, policy_errors = load_directory(POLICY_DIR)
    templates, template_errors = load_jsonl(TEMPLATE_FILE)
    evaluations, evaluation_errors = load_directory(EVALUATION_DIR)
    capabilities, capability_errors = load_jsonl(CAPABILITY_FILE)
    reviews, review_errors = load_jsonl(REVIEW_FILE)
    errors.extend(
        source_errors
        + evidence_errors
        + policy_errors
        + template_errors
        + evaluation_errors
        + capability_errors
        + review_errors
    )

    source_required = {
        "source_id",
        "authority",
        "title",
        "source_type",
        "jurisdiction",
        "version",
        "retrieved_at",
        "content_roles",
        "allowed_use",
        "prohibited_use",
        "license_status",
        "embedding_policy",
        "status",
    }
    evidence_required = {
        "evidence_id",
        "source_id",
        "domain",
        "topic",
        "population",
        "statement_type",
        "normalized_statement",
        "allowed_use",
        "prohibited_use",
        "source_locator",
        "keywords",
        "medical_interpretation_required",
        "embed",
        "review_status",
        "version",
        "status",
    }
    policy_required = {
        "policy_id",
        "capability_id",
        "domain",
        "intent",
        "risk_level",
        "priority",
        "condition",
        "required_context",
        "action",
        "allowed_claims",
        "prohibited_claims",
        "evidence_ids",
        "source_ids",
        "response_template_id",
        "activation_gate",
        "review_status",
        "version",
        "status",
    }
    template_required = {
        "template_id",
        "action",
        "required_sections",
        "forbidden_phrases",
        "requires_citation",
        "version",
        "status",
    }
    evaluation_required = {
        "case_id",
        "question",
        "structured_context",
        "expected_action",
        "expected_policy_ids",
        "required_evidence_ids",
        "prohibited_claims",
        "split",
        "status",
    }
    capability_required = {
        "capability_id",
        "domain",
        "name",
        "risk_level",
        "intended_outputs",
        "required_context",
        "required_evidence_roles",
        "required_reviewer_roles",
        "clinical_approval_required",
        "activation_status",
        "runtime_fail_action",
        "version",
        "status",
    }
    review_required = {
        "review_id",
        "capability_id",
        "review_scope",
        "required_reviewer_roles",
        "reviewer_refs",
        "policy_ids",
        "evidence_ids",
        "evaluation_case_ids",
        "decision",
        "decision_rationale",
        "protocol_version",
        "evidence_version",
        "decision_at",
        "valid_from",
        "valid_until",
        "version",
        "status",
    }

    for record in sources:
        require(record, source_required, errors)
    for record in evidence:
        require(record, evidence_required, errors)
    for record in policies:
        require(record, policy_required, errors)
    for record in templates:
        require(record, template_required, errors)
    for record in evaluations:
        require(record, evaluation_required, errors)
    for record in capabilities:
        require(record, capability_required, errors)
    for record in reviews:
        require(record, review_required, errors)

    source_index = index_unique(sources, "source_id", "source_id", errors)
    evidence_index = index_unique(evidence, "evidence_id", "evidence_id", errors)
    policy_index = index_unique(policies, "policy_id", "policy_id", errors)
    template_index = index_unique(templates, "template_id", "template_id", errors)
    evaluation_index = index_unique(evaluations, "case_id", "case_id", errors)
    capability_index = index_unique(capabilities, "capability_id", "capability_id", errors)
    index_unique(reviews, "review_id", "review_id", errors)

    reviews_by_capability: dict[str, list[Record]] = {}
    for review in reviews:
        capability_id = review.value.get("capability_id")
        reviews_by_capability.setdefault(str(capability_id), []).append(review)

    for record in sources:
        value = record.value
        url = value.get("url")
        local_path = value.get("local_path")
        if not url and not local_path:
            errors.append(f"{record.label}: source needs url or local_path")
        if url and not str(url).startswith("https://"):
            errors.append(f"{record.label}: source url must use https")
        if url and "slack.com" in str(url):
            errors.append(f"{record.label}: Slack URL cannot be an evidence source")
        if local_path and not (ROOT / str(local_path)).exists():
            errors.append(f"{record.label}: local_path does not exist: {local_path}")
        if value.get("status") == "ACTIVE" and value.get("license_status") in {"PENDING", "RESTRICTED"}:
            errors.append(f"{record.label}: restricted or pending-license source cannot be ACTIVE")

    embedded_count = 0
    for record in evidence:
        value = record.value
        source_id = value.get("source_id")
        source_record = source_index.get(source_id)
        if source_record is None:
            errors.append(f"{record.label}: unknown source_id {source_id}")
            continue
        if len(str(value.get("normalized_statement", "")).strip()) < 20:
            errors.append(f"{record.label}: normalized_statement is too short")
        if not value.get("keywords"):
            errors.append(f"{record.label}: keywords must not be empty")
        if value.get("embed"):
            embedded_count += 1
            if value.get("status") != "ACTIVE":
                errors.append(f"{record.label}: embedded evidence must be ACTIVE")
            if value.get("review_status") not in {"SOURCE_VERIFIED", "CLINICALLY_APPROVED"}:
                errors.append(f"{record.label}: embedded evidence needs source or clinical approval")
            if value.get("medical_interpretation_required") and value.get("review_status") != "CLINICALLY_APPROVED":
                errors.append(f"{record.label}: clinical interpretation evidence needs clinical approval before embedding")
            if source_record.value.get("status") != "ACTIVE":
                errors.append(f"{record.label}: embedded evidence source must be ACTIVE")
            if source_record.value.get("embedding_policy") not in ALLOWED_EMBEDDING_POLICIES:
                errors.append(f"{record.label}: source embedding policy does not allow embedding")

    for record in templates:
        action = record.value.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"{record.label}: unsupported template action {action}")

    for record in capabilities:
        value = record.value
        capability_id = str(value.get("capability_id"))
        clinical_required = value.get("clinical_approval_required") is True
        activation_status = value.get("activation_status")
        if value.get("runtime_fail_action") not in ALLOWED_ACTIONS:
            errors.append(f"{record.label}: unsupported runtime_fail_action {value.get('runtime_fail_action')}")
        if clinical_required and not value.get("required_reviewer_roles"):
            errors.append(f"{record.label}: clinical capability needs reviewer roles")
        if clinical_required and activation_status == "ACTIVE_SOURCE_VERIFIED":
            errors.append(f"{record.label}: clinical capability cannot activate on source review alone")
        approved_reviews = [
            review
            for review in reviews_by_capability.get(capability_id, [])
            if review.value.get("decision") == "APPROVED" and review.value.get("status") == "ACTIVE"
        ]
        if activation_status == "CLINICALLY_APPROVED" and not approved_reviews:
            errors.append(f"{record.label}: clinically approved capability needs an approved review")

    for record in reviews:
        value = record.value
        capability_id = value.get("capability_id")
        capability = capability_index.get(capability_id)
        if capability is None:
            errors.append(f"{record.label}: unknown review capability_id {capability_id}")
        elif not set(capability.value.get("required_reviewer_roles", [])).issubset(
            set(value.get("required_reviewer_roles", []))
        ):
            errors.append(f"{record.label}: review omits a capability reviewer role")
        for policy_id in value.get("policy_ids", []):
            policy = policy_index.get(policy_id)
            if policy is None:
                errors.append(f"{record.label}: unknown review policy_id {policy_id}")
            elif policy.value.get("capability_id") != capability_id:
                errors.append(f"{record.label}: reviewed policy belongs to another capability")
        for evidence_id in value.get("evidence_ids", []):
            if evidence_id not in evidence_index:
                errors.append(f"{record.label}: unknown review evidence_id {evidence_id}")
        for case_id in value.get("evaluation_case_ids", []):
            if case_id not in evaluation_index:
                errors.append(f"{record.label}: unknown review evaluation_case_id {case_id}")
        if value.get("decision") == "APPROVED":
            for field in (
                "decision_rationale",
                "protocol_version",
                "evidence_version",
                "decision_at",
                "valid_from",
                "valid_until",
            ):
                if not value.get(field):
                    errors.append(f"{record.label}: approved review needs {field}")
            if not value.get("reviewer_refs"):
                errors.append(f"{record.label}: approved review needs reviewer_refs")
            if not value.get("evidence_ids"):
                errors.append(f"{record.label}: approved review needs evidence_ids")

    for record in policies:
        value = record.value
        action = value.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"{record.label}: unsupported policy action {action}")
        if not isinstance(value.get("priority"), int):
            errors.append(f"{record.label}: priority must be an integer")
        if not isinstance(value.get("condition"), dict) or not value.get("condition"):
            errors.append(f"{record.label}: condition must be a non-empty object")
        if action in RESTRICTIVE_ACTIONS and not value.get("prohibited_claims"):
            errors.append(f"{record.label}: restrictive action needs prohibited_claims")
        capability_id = value.get("capability_id")
        capability = capability_index.get(capability_id)
        if capability is None:
            errors.append(f"{record.label}: unknown capability_id {capability_id}")
        elif capability.value.get("risk_level") != value.get("risk_level"):
            errors.append(f"{record.label}: policy risk_level must match capability risk_level")
        activation_gate = value.get("activation_gate")
        if not isinstance(activation_gate, dict):
            errors.append(f"{record.label}: activation_gate must be an object")
            activation_gate = {}
        clinical_required = activation_gate.get("clinical_approval_required") is True
        if clinical_required and activation_gate.get("required_review_status") != "CLINICALLY_APPROVED":
            errors.append(f"{record.label}: clinical gate must require CLINICALLY_APPROVED")
        if value.get("status") == "ACTIVE":
            allowed_review_statuses = {"SOURCE_VERIFIED", "CLINICALLY_APPROVED"}
            if value.get("review_status") not in allowed_review_statuses:
                errors.append(f"{record.label}: active policy lacks an executable review status")
            if clinical_required:
                if value.get("review_status") != "CLINICALLY_APPROVED":
                    errors.append(f"{record.label}: active clinical policy must be CLINICALLY_APPROVED")
                if capability and capability.value.get("activation_status") != "CLINICALLY_APPROVED":
                    errors.append(f"{record.label}: active clinical policy capability is not approved")
                approved_for_policy = any(
                    review.value.get("decision") == "APPROVED"
                    and review.value.get("status") == "ACTIVE"
                    and value.get("policy_id") in review.value.get("policy_ids", [])
                    for review in reviews_by_capability.get(str(capability_id), [])
                )
                if not approved_for_policy:
                    errors.append(f"{record.label}: active clinical policy is absent from approved review scope")
        for source_id in value.get("source_ids", []):
            if source_id not in source_index:
                errors.append(f"{record.label}: unknown policy source_id {source_id}")
        for evidence_id in value.get("evidence_ids", []):
            if evidence_id not in evidence_index:
                errors.append(f"{record.label}: unknown policy evidence_id {evidence_id}")
        template_id = value.get("response_template_id")
        template = template_index.get(template_id)
        if template is None:
            errors.append(f"{record.label}: unknown response_template_id {template_id}")
        elif template.value.get("action") != action:
            errors.append(
                f"{record.label}: policy action {action} does not match template action "
                f"{template.value.get('action')}"
            )

    for record in evaluations:
        value = record.value
        expected_action = value.get("expected_action")
        matched_actions: set[str] = set()
        for policy_id in value.get("expected_policy_ids", []):
            policy = policy_index.get(policy_id)
            if policy is None:
                errors.append(f"{record.label}: unknown expected policy_id {policy_id}")
            else:
                matched_actions.add(str(policy.value.get("action")))
        if matched_actions and expected_action not in matched_actions:
            errors.append(
                f"{record.label}: expected_action {expected_action} does not match policy actions "
                f"{sorted(matched_actions)}"
            )
        for evidence_id in value.get("required_evidence_ids", []):
            if evidence_id not in evidence_index:
                errors.append(f"{record.label}: unknown required evidence_id {evidence_id}")

    counts = {
        "sources": len(sources),
        "evidence": len(evidence),
        "embedded_evidence": embedded_count,
        "policies": len(policies),
        "capabilities": len(capabilities),
        "clinical_reviews": len(reviews),
        "templates": len(templates),
        "evaluation_cases": len(evaluations),
    }
    return errors, counts


def main() -> int:
    errors, counts = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        "OK: "
        + ", ".join(f"{name}={count}" for name, count in counts.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
