#!/usr/bin/env python3
"""Embed approved knowledge chunks through an OpenAI-compatible embeddings endpoint.

The endpoint contract is intentionally small:
request  {"model": "...", "input": ["..."]}
response {"data": [{"index": 0, "embedding": [..]}]}

User screening observations are never selected by this worker.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

try:
    import psycopg
except ImportError:  # pragma: no cover - clear runtime error for local setup
    psycopg = None


@dataclass(frozen=True)
class Chunk:
    id: str
    content: str


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def fetch_embeddings(endpoint: str, api_key: str, model: str, inputs: list[str]) -> list[list[float]]:
    payload = json.dumps({"model": model, "input": inputs}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"embedding endpoint returned HTTP {error.code}: {detail[:1000]}") from error

    rows = sorted(body.get("data", []), key=lambda row: row.get("index", 0))
    if len(rows) != len(inputs):
        raise RuntimeError(f"embedding count mismatch: requested {len(inputs)}, received {len(rows)}")
    return [row["embedding"] for row in rows]


def batched(items: list[Chunk], size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if psycopg is None:
        print("psycopg is missing; install requirements-vdb.txt", file=sys.stderr)
        return 2

    database_url = required_env("DATABASE_URL")
    model = os.getenv("EMBEDDING_MODEL", "embedding-model")
    expected_dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
    endpoint = api_key = ""
    if not args.dry_run:
        endpoint = required_env("EMBEDDING_API_URL")
        api_key = required_env("EMBEDDING_API_KEY")

    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            """
            SELECT kc.id::TEXT, kc.content
            FROM knowledge_chunk kc
            JOIN source_document sd ON sd.id = kc.source_document_id
            JOIN source_registry sr ON sr.id = sd.source_id
            WHERE kc.embedding IS NULL
              AND kc.is_retrievable = TRUE
              AND kc.review_status IN ('SOURCE_VERIFIED', 'CLINICALLY_APPROVED')
              AND sd.is_retrievable = TRUE
              AND sd.review_status IN ('SOURCE_VERIFIED', 'CLINICALLY_APPROVED')
              AND sr.is_active = TRUE
              AND sr.license_status = 'APPROVED'
            ORDER BY kc.created_at, kc.chunk_index
            LIMIT %s
            """,
            (max(1, args.limit),),
        ).fetchall()
        chunks = [Chunk(id=row[0], content=row[1]) for row in rows]

        print(f"pending chunks: {len(chunks)}")
        if args.dry_run or not chunks:
            return 0

        updated = 0
        for batch in batched(chunks, max(1, args.batch_size)):
            vectors = fetch_embeddings(endpoint, api_key, model, [chunk.content for chunk in batch])
            for chunk, vector in zip(batch, vectors, strict=True):
                if len(vector) != expected_dimension:
                    raise RuntimeError(
                        f"dimension mismatch for {chunk.id}: expected {expected_dimension}, got {len(vector)}"
                    )
                vector_literal = "[" + ",".join(format(float(value), ".10g") for value in vector) + "]"
                connection.execute(
                    """
                    UPDATE knowledge_chunk
                    SET embedding = %s::vector,
                        embedding_model = %s,
                        embedded_at = NOW()
                    WHERE id = %s::UUID
                    """,
                    (vector_literal, model, chunk.id),
                )
                updated += 1
            connection.commit()
            print(f"embedded: {updated}/{len(chunks)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

