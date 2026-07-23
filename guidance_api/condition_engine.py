from typing import Any, Dict


MISSING = object()


def get_path(facts: Dict[str, Any], path: str) -> Any:
    current: Any = facts
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def evaluate_condition(condition: Dict[str, Any], facts: Dict[str, Any]) -> bool:
    if "all" in condition:
        values = condition.get("all") or []
        return bool(values) and all(evaluate_condition(item, facts) for item in values)
    if "any" in condition:
        values = condition.get("any") or []
        return bool(values) and any(evaluate_condition(item, facts) for item in values)
    if "missing_any" in condition:
        return any(get_path(facts, path) is MISSING for path in condition.get("missing_any") or [])

    path = condition.get("field")
    operator = condition.get("operator")
    if not isinstance(path, str):
        return False
    actual = get_path(facts, path)
    expected = condition.get("value")
    if operator == "eq":
        return actual is not MISSING and actual == expected
    if operator == "neq":
        return actual is not MISSING and actual != expected
    if operator == "exists":
        return (actual is not MISSING) is bool(expected)
    if operator == "in":
        return actual is not MISSING and isinstance(expected, list) and actual in expected
    if operator == "contains":
        return actual is not MISSING and isinstance(actual, (list, str)) and expected in actual
    return False

