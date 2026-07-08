from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from doc_chunker.models import Chunk


class ChunkStore(ABC):
    """Storage abstraction for parsed/chunked documents.

    A concrete backend only needs to implement three small persistence
    primitives (`write_document`, `load_chunks`, `get_document_info`); the
    query methods that expand context after a search hit (`get_neighbors`,
    `get_section`, `search`) are implemented once here on top of those
    primitives, so a new backend (e.g. SQLite) only has to provide the
    three primitives to get the rest for free -- see
    tests/test_store_contract.py, which tests this shared behavior against
    `DocumentStore` and is written to be reusable against any future
    backend without modification.
    """

    @abstractmethod
    def write_document(
        self,
        *,
        doc_id: str,
        source_file: str,
        chunks: list[Chunk],
        parser: str,
        chunking: dict[str, Any],
    ) -> dict[str, Any]: ...

    @abstractmethod
    def load_chunks(self) -> list[Chunk]:
        """Return every chunk currently in the store, in write order."""

    @abstractmethod
    def get_document_info(self, doc_id: str) -> dict[str, Any] | None:
        """Return the manifest entry recorded for `doc_id`, or None."""

    def get_by_document(self, doc_id: str) -> list[Chunk]:
        return [chunk for chunk in self.load_chunks() if chunk.doc_id == doc_id]

    def get_neighbors(self, chunk_id: str, *, before: int = 1, after: int = 1) -> list[Chunk]:
        """Walk prev_chunk_id/next_chunk_id from `chunk_id` to build a
        window of surrounding chunks (the target chunk included), used to
        restore context around a search hit. Never crosses a document
        boundary even if two documents' id chains happened to collide."""
        index = {chunk.chunk_id: chunk for chunk in self.load_chunks()}
        target = index.get(chunk_id)
        if target is None:
            raise KeyError(f"chunk not found: {chunk_id}")

        prevs: list[Chunk] = []
        cursor = target
        for _ in range(before):
            if cursor.prev_chunk_id is None:
                break
            candidate = index.get(cursor.prev_chunk_id)
            if candidate is None or candidate.doc_id != target.doc_id:
                break
            prevs.append(candidate)
            cursor = candidate
        prevs.reverse()

        nexts: list[Chunk] = []
        cursor = target
        for _ in range(after):
            if cursor.next_chunk_id is None:
                break
            candidate = index.get(cursor.next_chunk_id)
            if candidate is None or candidate.doc_id != target.doc_id:
                break
            nexts.append(candidate)
            cursor = candidate

        return prevs + [target] + nexts

    def get_section(self, chunk_id: str) -> list[Chunk]:
        """Dynamic small-to-big aggregation: return every chunk in the same
        document that shares `chunk_id`'s heading_path, in document order.
        This is a logical "parent" view over the existing heading_path
        field rather than a physically stored parent block -- see
        docs/process/TODO.md item 2 for the trade-off this encodes."""
        chunks = self.load_chunks()
        index = {chunk.chunk_id: chunk for chunk in chunks}
        target = index.get(chunk_id)
        if target is None:
            raise KeyError(f"chunk not found: {chunk_id}")
        return [
            chunk
            for chunk in chunks
            if chunk.doc_id == target.doc_id and chunk.heading_path == target.heading_path
        ]

    def search(
        self, query: str, *, limit: int = 5, expand: str | None = None
    ) -> list[dict[str, Any]]:
        if expand not in (None, "neighbors", "section"):
            raise ValueError(f"Unsupported expand mode: {expand!r} (use 'neighbors' or 'section')")
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[dict[str, Any]] = []
        for chunk in self.load_chunks():
            haystack = chunk.text.lower()
            if needle in haystack or all(token in haystack for token in needle.split()):
                if expand is None:
                    matches.append(chunk.to_dict())
                else:
                    context = (
                        self.get_section(chunk.chunk_id)
                        if expand == "section"
                        else self.get_neighbors(chunk.chunk_id)
                    )
                    matches.append(
                        {
                            "chunk": chunk.to_dict(),
                            "expand": expand,
                            "context": [c.to_dict() for c in context],
                        }
                    )
            if len(matches) >= limit:
                break
        return matches


class DocumentStore(ChunkStore):
    """Local-file backend: one manifest.json + one chunks.jsonl per store
    directory. This is the required "at least one local-file (JSONL/SQLite)
    backend" implementation of the ChunkStore abstraction above."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.manifest_path = self.root / "manifest.json"
        self.chunks_path = self.root / "chunks.jsonl"

    def write_document(
        self,
        *,
        doc_id: str,
        source_file: str,
        chunks: list[Chunk],
        parser: str,
        chunking: dict[str, Any],
    ) -> dict[str, Any]:
        self.root.mkdir(parents=True, exist_ok=True)
        existing = [chunk for chunk in self.load_chunks() if chunk.doc_id != doc_id]
        all_chunks = existing + chunks
        with self.chunks_path.open("w", encoding="utf-8") as handle:
            for chunk in all_chunks:
                handle.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")

        manifest = self._load_manifest()
        docs = [doc for doc in manifest.get("documents", []) if doc.get("doc_id") != doc_id]
        doc_entry = {
            "doc_id": doc_id,
            "source_file": source_file,
            "parser": parser,
            "chunk_count": len(chunks),
            "chunking": chunking,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        docs.append(doc_entry)
        manifest = {
            "chunk_count": len(all_chunks),
            "documents": docs,
        }
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def load_chunks(self) -> list[Chunk]:
        if not self.chunks_path.exists():
            return []
        chunks: list[Chunk] = []
        with self.chunks_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    chunks.append(Chunk.from_dict(json.loads(line)))
        return chunks

    def get_document_info(self, doc_id: str) -> dict[str, Any] | None:
        manifest = self._load_manifest()
        for doc in manifest.get("documents", []):
            if doc.get("doc_id") == doc_id:
                return doc
        return None

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"documents": []}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))
