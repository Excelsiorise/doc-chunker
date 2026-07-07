from __future__ import annotations

from pathlib import Path

from doc_chunker.models import Chunk
from doc_chunker.store import DocumentStore


def test_store_writes_manifest_and_round_trips_chunks(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "index")
    chunks = [
        Chunk(
            chunk_id="doc-1:0001",
            doc_id="doc-1",
            text="alpha beta",
            source_file="sample.txt",
            locator={"line": 1},
            heading_path=["Intro"],
            prev_chunk_id=None,
            next_chunk_id=None,
            metadata={"block_types": ["paragraph"]},
        )
    ]

    manifest = store.write_document(
        doc_id="doc-1",
        source_file="sample.txt",
        chunks=chunks,
        parser="text",
        chunking={"max_chars": 100, "overlap_chars": 10},
    )

    assert (tmp_path / "index" / "manifest.json").exists()
    assert (tmp_path / "index" / "chunks.jsonl").exists()
    assert manifest["chunk_count"] == 1
    assert store.load_chunks() == chunks


def test_store_search_returns_keyword_matches_with_metadata(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "index")
    store.write_document(
        doc_id="doc-1",
        source_file="sample.txt",
        chunks=[
            Chunk("doc-1:0001", "doc-1", "alpha beta", "sample.txt", {"line": 1}, [], None, "doc-1:0002", {}),
            Chunk("doc-1:0002", "doc-1", "gamma delta", "sample.txt", {"line": 2}, [], "doc-1:0001", None, {}),
        ],
        parser="text",
        chunking={"max_chars": 100, "overlap_chars": 0},
    )

    results = store.search("gamma")

    assert len(results) == 1
    assert results[0]["chunk_id"] == "doc-1:0002"
    assert results[0]["text"] == "gamma delta"
