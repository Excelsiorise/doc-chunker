"""Contract tests for the query methods ChunkStore implements once on top
of write_document/load_chunks (get_neighbors, get_section, search+expand,
get_document_info). Only DocumentStore (JSONL) exists as a backend today,
but the `store` fixture is parametrized on purpose: it stays a one-line
addition (`_make_store`) to re-run this whole suite unmodified against any
future backend (e.g. SQLite), which is the actual point of pulling these
methods onto the ChunkStore ABC in the first place -- see DECISIONS.md
D008."""

from __future__ import annotations

from pathlib import Path

import pytest

from doc_chunker.models import Chunk
from doc_chunker.store import ChunkStore, DocumentStore


def _make_store(kind: str, tmp_path: Path) -> ChunkStore:
    if kind == "jsonl":
        return DocumentStore(tmp_path / "index")
    raise ValueError(kind)


def _seed(store: ChunkStore, doc_id: str = "doc-1") -> list[Chunk]:
    chunks = [
        Chunk(
            f"{doc_id}:0001", doc_id, "Intro paragraph one.", "s.txt", {"line": 1},
            ["Intro"], None, f"{doc_id}:0002", {},
        ),
        Chunk(
            f"{doc_id}:0002", doc_id, "Intro paragraph two.", "s.txt", {"line": 2},
            ["Intro"], f"{doc_id}:0001", f"{doc_id}:0003", {},
        ),
        Chunk(
            f"{doc_id}:0003", doc_id, "Details paragraph one, needle here.", "s.txt", {"line": 3},
            ["Details"], f"{doc_id}:0002", None, {},
        ),
    ]
    store.write_document(
        doc_id=doc_id, source_file="s.txt", chunks=chunks, parser="text",
        chunking={"max_chars": 100, "overlap_chars": 0},
    )
    return chunks


@pytest.fixture(params=["jsonl"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> ChunkStore:
    return _make_store(request.param, tmp_path)


def test_get_by_document_filters_by_doc_id(store: ChunkStore) -> None:
    _seed(store, "doc-1")
    _seed(store, "doc-2")

    result = store.get_by_document("doc-1")

    assert {c.chunk_id for c in result} == {"doc-1:0001", "doc-1:0002", "doc-1:0003"}


def test_get_neighbors_returns_window_around_target(store: ChunkStore) -> None:
    _seed(store)

    window = store.get_neighbors("doc-1:0002", before=1, after=1)

    assert [c.chunk_id for c in window] == ["doc-1:0001", "doc-1:0002", "doc-1:0003"]


def test_get_neighbors_clamps_at_document_edges(store: ChunkStore) -> None:
    _seed(store)

    window = store.get_neighbors("doc-1:0001", before=2, after=0)

    assert [c.chunk_id for c in window] == ["doc-1:0001"]


def test_get_neighbors_missing_chunk_raises(store: ChunkStore) -> None:
    _seed(store)

    with pytest.raises(KeyError):
        store.get_neighbors("doc-1:9999")


def test_get_section_groups_by_heading_path(store: ChunkStore) -> None:
    _seed(store)

    section = store.get_section("doc-1:0001")

    assert [c.chunk_id for c in section] == ["doc-1:0001", "doc-1:0002"]


def test_search_without_expand_returns_flat_chunk_dicts(store: ChunkStore) -> None:
    _seed(store)

    results = store.search("needle")

    assert len(results) == 1
    assert results[0]["chunk_id"] == "doc-1:0003"
    assert "context" not in results[0]


def test_search_with_expand_neighbors_includes_context(store: ChunkStore) -> None:
    _seed(store)

    results = store.search("needle", expand="neighbors")

    assert len(results) == 1
    assert results[0]["chunk"]["chunk_id"] == "doc-1:0003"
    assert [c["chunk_id"] for c in results[0]["context"]] == ["doc-1:0002", "doc-1:0003"]


def test_search_with_expand_section_includes_whole_section(store: ChunkStore) -> None:
    _seed(store)

    results = store.search("Intro paragraph one", expand="section")

    assert len(results) == 1
    assert [c["chunk_id"] for c in results[0]["context"]] == ["doc-1:0001", "doc-1:0002"]


def test_search_rejects_unknown_expand_mode(store: ChunkStore) -> None:
    _seed(store)

    with pytest.raises(ValueError):
        store.search("needle", expand="bogus")


def test_get_document_info_roundtrips_chunking_metadata(store: ChunkStore) -> None:
    chunks = [Chunk("doc-1:0001", "doc-1", "a", "s.txt", {}, [], None, None, {})]
    store.write_document(
        doc_id="doc-1", source_file="s.txt", chunks=chunks, parser="text",
        chunking={"max_chars": 100, "overlap_chars": 0},
    )

    info = store.get_document_info("doc-1")

    assert info is not None
    assert info["chunking"]["max_chars"] == 100
    assert store.get_document_info("missing-doc") is None
