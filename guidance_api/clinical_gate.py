from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Set

from .condition_engine import evaluate_condition
from .knowledge import KnowledgeRepository
from .models import GuidanceDecision, GuidanceRequest


@dataclass(frozen=True)
class GateEvaluation:
    decision: GuidanceDecision
    capability: Dict[str, Any]
    policy: Optional[Dict[str, Any]]
    review: Optional[Dict[str, Any]]


def _context_keys(value: Any, prefix: str = "") -> Set[str]:
    keys: Set[str] = set()
    if not isinstance(value, dict):
        return keys
    for key, child in value.items():
        full = "%s.%s" % (prefix, key) if prefix else str(key)
        keys.add(full)
        keys.add(str(key))
        keys.update(_context_keys(child, full))
    return keys


def _date_in_range(review: Dict[str, Any], as_of: date) -> bool:
    valid_from = review.get("valid_from")
    valid_until = review.get("valid_until")
    if not valid_from or not valid_until:
        return False
    return date.fromisoformat(valid_from) <= as_of <= date.fromisoformat(valid_until)


class ClinicalApprovalGate:
    def __init__(self, repository: KnowledgeRepository, as_of: Optional[date] = None):
        self.repository = repository
        self.as_of = as_of

    def evaluate(self, request: GuidanceRequest, capability_id: str) -> GateEvaluation:
        capability = self.repository.capability(capability_id)
        policies = self.repository.policies_for(capability_id)
        required_context = list(capability.get("required_context", []))
        available_keys = _context_keys(request.context)
        missing_context = [key for key in required_context if key not in available_keys]
        clinical_required = capability.get("clinical_approval_required") is True

        if not clinical_required:
            facts = self._facts(request, capability_id, False, missing_context)
            policy = self._select_nonclinical_policy(policies, facts, missing_context)
            allowed = not missing_context and capability.get("status") == "ACTIVE"
            action = policy["action"] if policy else ("ASK_CONTEXT" if missing_context else "INSUFFICIENT_EVIDENCE")
            return GateEvaluation(
                decision=GuidanceDecision(
                    request_id=request.request_id,
                    capability_id=capability_id,
                    risk_level=capability["risk_level"],
                    allowed=allowed,
                    action=action,
                    policy_id=policy.get("policy_id") if policy else None,
                    reason="required context is missing" if missing_context else "source-verified capability",
                    required_context=required_context,
                    missing_context=missing_context,
                ),
                capability=capability,
                policy=policy,
                review=None,
            )

        review = self._approved_review(capability_id)
        approval_exists = review is not None
        facts = self._facts(request, capability_id, approval_exists, missing_context)
        policy = self._approved_policy(policies, review, facts)
        capability_approved = (
            capability.get("activation_status") == "CLINICALLY_APPROVED"
            and capability.get("status") == "ACTIVE"
        )
        if not capability_approved or review is None or policy is None:
            fallback = self._fallback_policy(policies, facts)
            action = fallback.get("action", capability.get("runtime_fail_action", "CLINICAL_REVIEW_REQUIRED")) if fallback else capability.get("runtime_fail_action", "CLINICAL_REVIEW_REQUIRED")
            return GateEvaluation(
                decision=GuidanceDecision(
                    request_id=request.request_id,
                    capability_id=capability_id,
                    risk_level=capability["risk_level"],
                    allowed=False,
                    action=action,
                    policy_id=fallback.get("policy_id") if fallback else None,
                    reason="no active clinical approval covers this capability",
                    required_context=required_context,
                    missing_context=missing_context,
                ),
                capability=capability,
                policy=fallback,
                review=None,
            )

        if missing_context:
            return GateEvaluation(
                decision=GuidanceDecision(
                    request_id=request.request_id,
                    capability_id=capability_id,
                    risk_level=capability["risk_level"],
                    allowed=False,
                    action="ASK_CONTEXT",
                    policy_id=policy["policy_id"],
                    clinical_review_id=review["review_id"],
                    protocol_version=review["protocol_version"],
                    reason="clinical approval exists but required context is missing",
                    required_context=required_context,
                    missing_context=missing_context,
                ),
                capability=capability,
                policy=policy,
                review=review,
            )

        return GateEvaluation(
            decision=GuidanceDecision(
                request_id=request.request_id,
                capability_id=capability_id,
                risk_level=capability["risk_level"],
                allowed=True,
                action=policy["action"],
                policy_id=policy["policy_id"],
                clinical_review_id=review["review_id"],
                protocol_version=review["protocol_version"],
                reason="request is covered by an active clinical approval",
                required_context=required_context,
                missing_context=[],
            ),
            capability=capability,
            policy=policy,
            review=review,
        )

    def _approved_review(self, capability_id: str) -> Optional[Dict[str, Any]]:
        as_of = self.as_of or date.today()
        for review in self.repository.reviews_for(capability_id):
            if (
                review.get("decision") == "APPROVED"
                and review.get("status") == "ACTIVE"
                and review.get("reviewer_refs")
                and review.get("protocol_version")
                and review.get("evidence_version")
                and _date_in_range(review, as_of)
            ):
                return review
        return None

    @staticmethod
    def _approved_policy(
        policies: List[Dict[str, Any]],
        review: Optional[Dict[str, Any]],
        facts: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if review is None:
            return None
        approved_ids = set(review.get("policy_ids", []))
        for policy in policies:
            gate = policy.get("activation_gate") or {}
            if (
                policy.get("policy_id") in approved_ids
                and policy.get("status") == "ACTIVE"
                and policy.get("review_status") == "CLINICALLY_APPROVED"
                and gate.get("clinical_approval_required") is True
                and evaluate_condition(policy.get("condition") or {}, facts)
            ):
                return policy
        return None

    @staticmethod
    def _fallback_policy(policies: List[Dict[str, Any]], facts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        active = [
            item
            for item in policies
            if item.get("status") == "ACTIVE"
            and not (item.get("activation_gate") or {}).get("clinical_approval_required")
            and evaluate_condition(item.get("condition") or {}, facts)
        ]
        return max(active, key=lambda item: item.get("priority", 0), default=None)

    @staticmethod
    def _select_nonclinical_policy(
        policies: List[Dict[str, Any]],
        facts: Dict[str, Any],
        missing_context: List[str],
    ) -> Optional[Dict[str, Any]]:
        active = [item for item in policies if item.get("status") == "ACTIVE"]
        if missing_context:
            ask = [
                item
                for item in active
                if item.get("action") == "ASK_CONTEXT"
                and evaluate_condition(item.get("condition") or {}, facts)
            ]
            return max(ask, key=lambda item: item.get("priority", 0), default=None)
        answer = [
            item
            for item in active
            if item.get("action") != "ASK_CONTEXT"
            and evaluate_condition(item.get("condition") or {}, facts)
        ]
        return max(answer, key=lambda item: item.get("priority", 0), default=None)

    @staticmethod
    def _facts(
        request: GuidanceRequest,
        capability_id: str,
        approved: bool,
        missing_context: List[str],
    ) -> Dict[str, Any]:
        supplied = dict(request.context)
        nested_context = dict(supplied.get("context") or {})
        for key, value in supplied.items():
            if key not in {"request", "record", "rules", "retrieval", "medication", "safety", "context"}:
                nested_context.setdefault(key, value)

        request_facts = dict(supplied.get("request") or {})
        record_facts = dict(supplied.get("record") or {})
        rules_facts = dict(supplied.get("rules") or {})
        retrieval_facts = dict(supplied.get("retrieval") or {})
        medication_facts = dict(supplied.get("medication") or {})
        safety_facts = dict(supplied.get("safety") or {})

        flags = {
            "CAP_GENERAL_WELLNESS": {"general_wellness": True, "condition_specific_exercise": False},
            "CAP_RECORDED_DATA_DISPLAY": {"recorded_data_lookup": True},
            "CAP_DIAGNOSTIC_SUPPORT": {"medical_diagnosis": True},
            "CAP_TREATMENT_GUIDANCE": {"treatment_or_retest_guidance": True},
            "CAP_CONDITION_SPECIFIC_EXERCISE": {"condition_specific_exercise": True},
            "CAP_SCREENING_INTERPRETATION": {"clinical_interpretation": True},
            "CAP_MEDICATION_DECISION_SUPPORT": {"requires_medication_decision": True},
            "CAP_URGENCY_TRIAGE": {"urgency_or_red_flag": True},
        }
        for key, value in flags.get(capability_id, {}).items():
            request_facts.setdefault(key, value)

        nested_context["clinical_input_complete"] = not missing_context
        record_facts.setdefault("user_confirmed", supplied.get("verified_result") is True or supplied.get("user_confirmed_record") is True)
        rules_facts.setdefault("version_match_for_observed_date", bool(supplied.get("reference_or_rule_version")))
        retrieval_facts.setdefault("approved_protocol_match", approved)
        medication_facts.setdefault("exact_reconciliation_complete", bool(supplied.get("exact_medication_list")))
        if capability_id == "CAP_OFFICIAL_DRUG_INFO":
            retrieval_facts.setdefault("exact_product_match", bool(supplied.get("exact_product_identifier")))
            retrieval_facts.setdefault("official_source", "MFDS_EASY_DRUG_API")
        if capability_id == "CAP_URGENCY_TRIAGE":
            safety_facts.setdefault("approved_red_flag_match", supplied.get("approved_red_flag_match") is True)

        return {
            "request": request_facts,
            "clinical_gate": {"approved_for_request_scope": approved},
            "context": nested_context,
            "record": record_facts,
            "rules": rules_facts,
            "retrieval": retrieval_facts,
            "medication": medication_facts,
            "safety": safety_facts,
        }
