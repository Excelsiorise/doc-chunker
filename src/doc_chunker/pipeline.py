from __future__ import annotations

import hashlib
import warnings
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
    store = DocumentStore(store_dir)

    blocks = parse_document(file_path)
    doc_id = _doc_id(file_path)

    requested_overlap = overlap_chars
    if overlap_chars >= max_chars:
        overlap_chars = max(0, max_chars // 5)
        warnings.warn(
            f"overlap_chars ({requested_overlap}) >= max_chars ({max_chars}); "
            f"clamped to {overlap_chars}. This is recorded in the manifest "
            "instead of being silently applied.",
            stacklevel=2,
        )
    config = ChunkingConfig(max_chars=max_chars, overlap_chars=overlap_chars)
    chunks = chunk_blocks(blocks, doc_id=doc_id, config=config)

    chunking_meta: dict[str, Any] = {
        "max_chars": max_chars,
        "overlap_chars": overlap_chars,
    }
    if requested_overlap != overlap_chars:
        chunking_meta["requested_overlap_chars"] = requested_overlap
        chunking_meta["overlap_adjusted"] = True

    manifest = store.write_document(
        doc_id=doc_id,
        source_file=str(file_path),
        chunks=chunks,
        parser=parser_name(file_path),
        chunking=chunking_meta,
    )
    return {
        "ok": True,
        "doc_id": doc_id,
        "chunk_count": len(chunks),
        "manifest": manifest,
    }


def _doc_id(path: Path) -> str:
    resolved = str(path.resolve()).encode("utf-8")
    digest = hashlib.sha1(resolved).hexdigest()[:10]
    stem = "".join(ch if ch.isalnum() else "-" for ch in path.stem.lower()).strip("-") or "document"
    return f"{stem}-{digest}"
