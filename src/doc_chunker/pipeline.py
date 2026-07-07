from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from doc_chunker.chunker import ChunkingConfig, chunk_blocks
from doc_chunker.parsers import parse_document, parser_name
from doc_chunker.store import DocumentStore


def ingest_document(
    path: str | Path,
    *,
    store_dir: str | Path,
    max_chars: int = 1000,
    overlap_chars: int = 150,
) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")
    blocks = parse_document(file_path)
    doc_id = _doc_id(file_path)
    if overlap_chars >= max_chars:
        overlap_chars = max(0, max_chars // 5)
    config = ChunkingConfig(max_chars=max_chars, overlap_chars=overlap_chars)
    chunks = chunk_blocks(blocks, doc_id=doc_id, config=config)
    store = DocumentStore(store_dir)
    manifest = store.write_document(
        doc_id=doc_id,
        source_file=str(file_path),
        chunks=chunks,
        parser=parser_name(file_path),
        chunking={"max_chars": max_chars, "overlap_chars": overlap_chars},
    )
    return {"ok": True, "doc_id": doc_id, "chunk_count": len(chunks), "manifest": manifest}


def _doc_id(path: Path) -> str:
    resolved = str(path.resolve()).encode("utf-8")
    digest = hashlib.sha1(resolved).hexdigest()[:10]
    stem = "".join(ch if ch.isalnum() else "-" for ch in path.stem.lower()).strip("-") or "document"
    return f"{stem}-{digest}"
