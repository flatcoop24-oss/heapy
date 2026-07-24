#!/usr/bin/env python3
"""Build the minimal RAG-serving corpus from reviewed authoring chunks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTHORING_PATH = ROOT / "knowledge/chunks/screening-labs-v1.jsonl"
SERVING_PATH = ROOT / "vdb/corpus/screening_labs_rag_v1.jsonl"

APPROVED_REVIEW_STATUSES = {"SOURCE_VERIFIED", "CLINICALLY_APPROVED"}
TOP_LEVEL_FIELDS = {"chunk_id", "text", "text_sha256", "metadata"}
METADATA_FIELDS = {
    "item_codes",
    "domain",
    "safety_level",
    "evidence_ids",
    "version",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_embedding_text(chunk: dict[str, Any]) -> str:
    keywords = " · ".join(chunk["keywords"])
    return f"{chunk['heading']}\n\n{chunk['content']}\n\n키워드: {keywords}"


def build_record(chunk: dict[str, Any]) -> dict[str, Any]:
    text = build_embedding_text(chunk)
    return {
        "chunk_id": chunk["canonical_key"],
        "text": text,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "metadata": {
            "item_codes": chunk["item_codes"],
            "domain": chunk["domain"],
            "safety_level": chunk["safety_level"],
            "evidence_ids": chunk["evidence_ids"],
            "version": chunk["version"],
        },
    }


def build_records(authoring_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        build_record(chunk)
        for chunk in authoring_chunks
        if chunk["status"] == "ACTIVE"
        and chunk["review_status"] in APPROVED_REVIEW_STATUSES
    ]


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        name = record.get("chunk_id", f"serving line {index}")
        if set(record) != TOP_LEVEL_FIELDS:
            errors.append(
                f"{name}: serving fields must be exactly {sorted(TOP_LEVEL_FIELDS)}"
            )
            continue
        if name in seen_ids:
            errors.append(f"{name}: duplicate chunk_id")
        seen_ids.add(name)

        text = record["text"]
        if not isinstance(text, str) or len(text.strip()) < 80:
            errors.append(f"{name}: text must be a non-empty standalone explanation")
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if record["text_sha256"] != expected_hash:
            errors.append(f"{name}: text_sha256 does not match text")

        metadata = record["metadata"]
        if not isinstance(metadata, dict) or set(metadata) != METADATA_FIELDS:
            errors.append(
                f"{name}: metadata fields must be exactly {sorted(METADATA_FIELDS)}"
            )
            continue
        if not metadata["item_codes"]:
            errors.append(f"{name}: item_codes must not be empty")
        if not metadata["evidence_ids"]:
            errors.append(f"{name}: evidence_ids must not be empty")

    return errors


def render_jsonl(records: list[dict[str, Any]]) -> str:
    return (
        "\n".join(
            json.dumps(
                record,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for record in records
        )
        + "\n"
    )


def main() -> int:
    authoring_chunks = load_jsonl(AUTHORING_PATH)
    records = build_records(authoring_chunks)
    errors = validate_records(records)
    if errors:
        print("RAG serving chunk build failed")
        for error in errors:
            print(f"- {error}")
        return 1

    SERVING_PATH.parent.mkdir(parents=True, exist_ok=True)
    SERVING_PATH.write_text(render_jsonl(records), encoding="utf-8")
    print(
        "RAG serving chunk build passed: "
        f"{len(authoring_chunks)} authoring -> {len(records)} serving"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
