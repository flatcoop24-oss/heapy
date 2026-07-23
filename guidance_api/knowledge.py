import json
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_ROOT = ROOT / "knowledge"


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("%s:%s must be a JSON object" % (path, line_number))
        records.append(value)
    return records


def _load_dir(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for jsonl_path in sorted(path.glob("*.jsonl")):
        records.extend(_load_jsonl(jsonl_path))
    return records


def _index(records: Iterable[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for record in records:
        identifier = str(record[key])
        if identifier in result:
            raise ValueError("duplicate %s: %s" % (key, identifier))
        result[identifier] = record
    return result


class KnowledgeRepository:
    """Thread-safe, reloadable view of version-controlled guidance JSONL."""

    def __init__(self, root: Path = DEFAULT_KNOWLEDGE_ROOT):
        self.root = root
        self._lock = threading.RLock()
        self.reload()

    def reload(self) -> None:
        capabilities = _load_jsonl(self.root / "capabilities/clinical_capabilities.jsonl")
        reviews = _load_jsonl(self.root / "reviews/clinical_reviews.jsonl")
        policies = _load_dir(self.root / "policies")
        evidence = _load_dir(self.root / "evidence")
        with self._lock:
            self.capabilities = _index(capabilities, "capability_id")
            self.reviews = _index(reviews, "review_id")
            self.policies = _index(policies, "policy_id")
            self.evidence = _index(evidence, "evidence_id")

    def capability(self, capability_id: str) -> Dict[str, Any]:
        with self._lock:
            try:
                return dict(self.capabilities[capability_id])
            except KeyError as exc:
                raise KeyError("unknown capability: %s" % capability_id) from exc

    def policies_for(self, capability_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self.policies.values() if item["capability_id"] == capability_id]

    def reviews_for(self, capability_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self.reviews.values() if item["capability_id"] == capability_id]

    def evidence_by_ids(self, evidence_ids: Iterable[str]) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(self.evidence[item]) for item in evidence_ids if item in self.evidence]

    def capability_list(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self.capabilities.values()]

