from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from doc_chunker.models import Chunk


class DocumentStore:
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
            "version": 1,
            "chunk_count": len(all_chunks),
            "documents": docs,
            **doc_entry,
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

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches = []
        for chunk in self.load_chunks():
            haystack = chunk.text.lower()
            if needle in haystack or all(token in haystack for token in needle.split()):
                matches.append(chunk.to_dict())
            if len(matches) >= limit:
                break
        return matches

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"version": 1, "documents": []}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))
