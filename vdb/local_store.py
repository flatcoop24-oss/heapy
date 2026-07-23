"""Deterministic local vector index for development and CI.

The production target remains PostgreSQL + pgvector.  This module makes the
curated corpus immediately searchable without sending medical text to an
external service or requiring a running database.  It uses a stable Korean-
friendly feature-hashing vector, so the generated index is reproducible.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


FORMAT_VERSION = 1
DEFAULT_DIMENSION = 1536
EMBEDDING_MODEL = "local-korean-feature-hashing-v1"
UUID_NAMESPACE = uuid.UUID("6965fd21-78bf-4c64-9322-4f1e6768d3d7")
TOKEN_PATTERN = re.compile(r"[0-9a-zA-Z가-힣]+")
ALLOWED_ROUTES = {
    "SIMPLE_LOOKUP",
    "DRUG_LOOKUP",
    "COMPREHENSIVE_ANALYSIS",
    "PROACTIVE_CARE",
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def corpus_checksum(corpus: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(corpus)).hexdigest()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return " ".join(TOKEN_PATTERN.findall(normalized))


def _features(text: str) -> Iterable[tuple[str, float]]:
    """Yield whole-token and character n-gram features.

    Character n-grams make Korean inflections and spacing differences robust
    enough for local smoke tests while keeping the implementation dependency-
    free.  This is a development index, not a substitute for a reviewed
    production embedding model.
    """

    for token in normalize_text(text).split():
        yield f"word:{token}", 1.8
        padded = f"^{token}$"
        for size, weight in ((2, 0.45), (3, 0.65), (4, 0.75)):
            if len(padded) < size:
                continue
            for start in range(len(padded) - size + 1):
                yield f"char{size}:{padded[start:start + size]}", weight


def embed_text(text: str, dimension: int = DEFAULT_DIMENSION) -> list[float]:
    if dimension <= 0:
        raise ValueError("dimension must be positive")

    vector = [0.0] * dimension
    counts: Counter[str] = Counter()
    weights: dict[str, float] = {}
    for feature, weight in _features(text):
        counts[feature] += 1
        weights[feature] = weight

    for feature, count in counts.items():
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        position = int.from_bytes(digest[:8], "big") % dimension
        sign = 1.0 if digest[8] & 1 else -1.0
        term_frequency = 1.0 + math.log(count)
        vector[position] += sign * weights[feature] * term_frequency

    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [round(value / norm, 10) for value in vector]
    return vector


def _chunk_search_text(chunk: dict[str, Any]) -> str:
    keywords = " ".join(chunk.get("keywords", []))
    # Repeating controlled keywords intentionally gives exact medical terms
    # more weight than generic prose in the local development index.
    return " ".join(
        [
            chunk.get("heading", ""),
            keywords,
            keywords,
            chunk.get("content", ""),
        ]
    )


def build_index(corpus: dict[str, Any], dimension: int = DEFAULT_DIMENSION) -> dict[str, Any]:
    document = corpus["document"]
    document_id = uuid.uuid5(UUID_NAMESPACE, document["external_document_id"])
    indexed_chunks: list[dict[str, Any]] = []

    for chunk_index, chunk in enumerate(corpus["chunks"]):
        chunk_id = uuid.uuid5(
            UUID_NAMESPACE,
            f"{document['external_document_id']}:{chunk['canonical_key']}:v1",
        )
        content_hash = hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()
        indexed_chunks.append(
            {
                "id": str(chunk_id),
                "source_document_id": str(document_id),
                "chunk_index": chunk_index,
                "chunk_version": 1,
                "canonical_key": chunk["canonical_key"],
                "heading": chunk["heading"],
                "domain": chunk["domain"],
                "section_type": chunk["section_type"],
                "content": chunk["content"],
                "content_hash": content_hash,
                "keywords": chunk["keywords"],
                "route_scope": chunk["route_scope"],
                "safety_level": chunk["safety_level"],
                "review_status": chunk["review_status"],
                "is_retrievable": chunk.get("is_retrievable", True),
                "evidence": chunk["evidence"],
                "embedding": embed_text(_chunk_search_text(chunk), dimension),
            }
        )

    return {
        "format_version": FORMAT_VERSION,
        "embedding_model": EMBEDDING_MODEL,
        "vector_dimension": dimension,
        "corpus_sha256": corpus_checksum(corpus),
        "document": {
            "id": str(document_id),
            "source_code": document["source_code"],
            "external_document_id": document["external_document_id"],
            "title": document["title"],
            "version_label": document["version_label"],
            "effective_from": document["effective_from"],
            "source_url": document.get("source_url"),
            "review_status": document["review_status"],
            "clinical_review_status": document["clinical_review_status"],
            "citation_label": document["citation_label"],
            "is_retrievable": document.get("is_retrievable", False),
        },
        "chunks": indexed_chunks,
    }


def write_index(index: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vector dimensions do not match")
    return sum(a * b for a, b in zip(left, right, strict=True))


def _keyword_score(query: str, chunk: dict[str, Any]) -> float:
    normalized_query = normalize_text(query)
    if not normalized_query:
        return 0.0

    query_tokens = set(normalized_query.split())
    heading_tokens = set(normalize_text(chunk["heading"]).split())
    keyword_tokens = {
        normalize_text(keyword)
        for keyword in chunk.get("keywords", [])
        if normalize_text(keyword)
    }
    exact_hits = sum(1 for keyword in keyword_tokens if keyword in normalized_query)
    token_hits = len(query_tokens & heading_tokens)
    return min(1.0, (0.35 * exact_hits) + (0.2 * token_hits))


def search_index(
    index: dict[str, Any],
    query: str,
    *,
    route: str = "SIMPLE_LOOKUP",
    domain: str | None = None,
    limit: int = 5,
    min_score: float = 0.04,
) -> list[dict[str, Any]]:
    route = route.upper()
    if route not in ALLOWED_ROUTES:
        raise ValueError(f"unsupported route: {route}")
    if not query.strip():
        return []

    dimension = int(index["vector_dimension"])
    query_vector = embed_text(query, dimension)
    results: list[dict[str, Any]] = []
    document = index["document"]
    if not document.get("is_retrievable", False):
        return []
    if document.get("review_status") not in {"SOURCE_VERIFIED", "CLINICALLY_APPROVED"}:
        return []

    for chunk in index["chunks"]:
        if not chunk.get("is_retrievable", False):
            continue
        if route not in chunk["route_scope"]:
            continue
        if domain and chunk["domain"] != domain.upper():
            continue
        if route in {"COMPREHENSIVE_ANALYSIS", "PROACTIVE_CARE"}:
            if chunk["review_status"] != "CLINICALLY_APPROVED":
                continue
            if document["clinical_review_status"] != "APPROVED":
                continue

        vector_score = max(0.0, cosine_similarity(query_vector, chunk["embedding"]))
        keyword_score = _keyword_score(query, chunk)
        score = (0.8 * vector_score) + (0.2 * keyword_score)
        if score < min_score:
            continue
        results.append(
            {
                "chunk_id": chunk["id"],
                "canonical_key": chunk["canonical_key"],
                "heading": chunk["heading"],
                "content": chunk["content"],
                "domain": chunk["domain"],
                "section_type": chunk["section_type"],
                "safety_level": chunk["safety_level"],
                "review_status": chunk["review_status"],
                "evidence": chunk["evidence"],
                "source_title": document["title"],
                "source_url": document.get("source_url"),
                "citation_label": document["citation_label"],
                "score": round(score, 6),
                "vector_score": round(vector_score, 6),
                "keyword_score": round(keyword_score, 6),
            }
        )

    results.sort(key=lambda row: (-row["score"], row["canonical_key"]))
    return results[: max(1, min(limit, 20))]


def get_by_key(
    index: dict[str, Any],
    canonical_key: str,
    *,
    route: str = "SIMPLE_LOOKUP",
) -> dict[str, Any] | None:
    route = route.upper()
    if route not in ALLOWED_ROUTES:
        raise ValueError(f"unsupported route: {route}")
    document = index["document"]
    if not document.get("is_retrievable", False):
        return None
    if document.get("review_status") not in {"SOURCE_VERIFIED", "CLINICALLY_APPROVED"}:
        return None
    for chunk in index["chunks"]:
        if chunk["canonical_key"] != canonical_key.upper():
            continue
        if not chunk.get("is_retrievable", False) or route not in chunk["route_scope"]:
            return None
        if route in {"COMPREHENSIVE_ANALYSIS", "PROACTIVE_CARE"}:
            if chunk["review_status"] != "CLINICALLY_APPROVED":
                return None
            if document["clinical_review_status"] != "APPROVED":
                return None
        return {
            **{key: value for key, value in chunk.items() if key != "embedding"},
            "source_title": index["document"]["title"],
            "source_url": index["document"].get("source_url"),
            "citation_label": index["document"]["citation_label"],
        }
    return None


def audit(corpus: dict[str, Any], index: dict[str, Any] | None = None) -> dict[str, Any]:
    chunks = corpus.get("chunks", [])
    issues: list[dict[str, str]] = []
    keys = [chunk.get("canonical_key", "") for chunk in chunks]
    content_hashes = [
        hashlib.sha256(chunk.get("content", "").encode("utf-8")).hexdigest()
        for chunk in chunks
    ]

    def add_issue(severity: str, code: str, message: str) -> None:
        issues.append({"severity": severity, "code": code, "message": message})

    if len(chunks) != 30:
        add_issue("HIGH", "CHUNK_COUNT", f"expected 30 chunks, found {len(chunks)}")
    if len(keys) != len(set(keys)):
        add_issue("CRITICAL", "DUPLICATE_KEY", "canonical_key must be unique")
    if len(content_hashes) != len(set(content_hashes)):
        add_issue("HIGH", "DUPLICATE_CONTENT", "duplicate chunk content detected")

    evidence_urls: set[str] = set()
    for position, chunk in enumerate(chunks):
        prefix = f"chunks[{position}]"
        if len(chunk.get("content", "").strip()) < 80:
            add_issue("HIGH", "CONTENT_TOO_SHORT", f"{prefix} has insufficient content")
        if not chunk.get("keywords"):
            add_issue("HIGH", "MISSING_KEYWORDS", f"{prefix} has no keywords")
        if not chunk.get("evidence"):
            add_issue("CRITICAL", "MISSING_EVIDENCE", f"{prefix} has no evidence")
        if not set(chunk.get("route_scope", [])) <= ALLOWED_ROUTES:
            add_issue("HIGH", "INVALID_ROUTE", f"{prefix} has an unsupported route")
        if chunk.get("review_status") not in {
            "DRAFT",
            "SOURCE_VERIFIED",
            "CLINICALLY_APPROVED",
            "REJECTED",
        }:
            add_issue("HIGH", "INVALID_REVIEW_STATUS", f"{prefix} has an invalid review status")
        for evidence in chunk.get("evidence", []):
            url = evidence.get("url", "")
            if not url.startswith("https://"):
                add_issue("HIGH", "INVALID_EVIDENCE_URL", f"{prefix} has invalid evidence URL")
            else:
                evidence_urls.add(url)

    index_summary: dict[str, Any] | None = None
    if index is not None:
        dimension = int(index.get("vector_dimension", 0))
        indexed_chunks = index.get("chunks", [])
        invalid_vectors = 0
        for chunk in indexed_chunks:
            vector = chunk.get("embedding", [])
            norm = math.sqrt(sum(float(value) ** 2 for value in vector))
            if len(vector) != dimension or not math.isclose(norm, 1.0, abs_tol=1e-6):
                invalid_vectors += 1
        if index.get("corpus_sha256") != corpus_checksum(corpus):
            add_issue("CRITICAL", "STALE_INDEX", "index checksum does not match the corpus")
        if len(indexed_chunks) != len(chunks):
            add_issue("CRITICAL", "INDEX_COVERAGE", "index does not cover every corpus chunk")
        if invalid_vectors:
            add_issue("CRITICAL", "INVALID_VECTOR", f"{invalid_vectors} vectors are invalid")
        index_summary = {
            "format_version": index.get("format_version"),
            "embedding_model": index.get("embedding_model"),
            "vector_dimension": dimension,
            "indexed_chunk_count": len(indexed_chunks),
            "invalid_vector_count": invalid_vectors,
            "corpus_checksum_matches": index.get("corpus_sha256") == corpus_checksum(corpus),
        }

    blocking = [issue for issue in issues if issue["severity"] in {"CRITICAL", "HIGH"}]
    return {
        "status": "PASS" if not blocking else "FAIL",
        "dataset": {
            "title": corpus.get("document", {}).get("title"),
            "version_label": corpus.get("document", {}).get("version_label"),
            "grain": "one knowledge chunk per canonical health-screening topic",
            "chunk_count": len(chunks),
            "unique_canonical_key_count": len(set(keys)),
            "distinct_evidence_url_count": len(evidence_urls),
            "review_status_counts": dict(
                sorted(Counter(chunk.get("review_status", "MISSING") for chunk in chunks).items())
            ),
        },
        "index": index_summary,
        "issues": issues,
        "limitations": [
            "The local feature-hashing index is for development and CI smoke tests.",
            "Production semantic retrieval still requires approved 1536-dimensional embeddings in pgvector.",
            "SOURCE_VERIFIED chunks are educational content and are not clinically approved for comprehensive analysis.",
            "Personal screening observations must remain outside the knowledge vector index.",
        ],
    }
