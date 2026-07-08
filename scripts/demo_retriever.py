#!/usr/bin/env python
"""Minimal downstream consumer for a doc-chunker store.

Deliberately does NOT `import doc_chunker` -- this is the executable proof
that chunks.jsonl is a real, independent export contract a downstream
retrieval/generation module can consume on its own (docs/process/TODO.md
P0-5 / P1-10), not an internal detail that only this package can read.

Usage:
    python scripts/demo_retriever.py <store_dir> <query> [--expand neighbors|section]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_chunks(store_dir: Path) -> list[dict]:
    chunks_path = store_dir / "chunks.jsonl"
    with chunks_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def search(chunks: list[dict], query: str, limit: int = 3) -> list[dict]:
    needle = query.lower()
    tokens = needle.split()
    return [
        chunk
        for chunk in chunks
        if needle in chunk["text"].lower() or all(t in chunk["text"].lower() for t in tokens)
    ][:limit]


def expand_section(chunks: list[dict], hit: dict) -> list[dict]:
    return [c for c in chunks if c["doc_id"] == hit["doc_id"] and c["heading_path"] == hit["heading_path"]]


def expand_neighbors(chunks: list[dict], hit: dict) -> list[dict]:
    by_id = {c["chunk_id"]: c for c in chunks}
    window = [hit]
    if hit["prev_chunk_id"] in by_id:
        window.insert(0, by_id[hit["prev_chunk_id"]])
    if hit["next_chunk_id"] in by_id:
        window.append(by_id[hit["next_chunk_id"]])
    return window


def cite(chunk: dict) -> str:
    section = " > ".join(chunk["heading_path"]) or "(no heading)"
    return f"{chunk['source_file']} | {chunk['locator']} | {section}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store_dir", type=Path)
    parser.add_argument("query")
    parser.add_argument("--expand", choices=["neighbors", "section"], default=None)
    args = parser.parse_args()

    chunks = load_chunks(args.store_dir)
    hits = search(chunks, args.query)
    if not hits:
        print(f"No matches for {args.query!r} in {args.store_dir}")
        sys.exit(1)

    for hit in hits:
        context = (
            expand_section(chunks, hit)
            if args.expand == "section"
            else expand_neighbors(chunks, hit)
            if args.expand == "neighbors"
            else [hit]
        )
        print(f"--- hit: {cite(hit)} ---")
        for chunk in context:
            marker = "*" if chunk is hit else " "
            print(f"{marker} [{cite(chunk)}] {chunk['text']}")
        print()


if __name__ == "__main__":
    main()
