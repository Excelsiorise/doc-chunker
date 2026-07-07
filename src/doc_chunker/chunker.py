from __future__ import annotations

import re
from dataclasses import dataclass

from doc_chunker.models import Chunk, DocumentBlock


@dataclass(frozen=True)
class ChunkingConfig:
    max_chars: int = 1000
    overlap_chars: int = 150

    def __post_init__(self) -> None:
        if self.max_chars < 40:
            raise ValueError("max_chars must be at least 40")
        if self.overlap_chars < 0:
            raise ValueError("overlap_chars must be >= 0")
        if self.overlap_chars >= self.max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")


def chunk_blocks(
    blocks: list[DocumentBlock],
    *,
    doc_id: str,
    config: ChunkingConfig | None = None,
) -> list[Chunk]:
    cfg = config or ChunkingConfig()
    chunks: list[Chunk] = []
    buffer: list[DocumentBlock] = []
    buffer_text = ""

    def flush() -> None:
        nonlocal buffer, buffer_text
        if not buffer_text.strip():
            buffer = []
            buffer_text = ""
            return
        _append_chunk(chunks, doc_id, buffer, buffer_text.strip())
        buffer = []
        buffer_text = ""

    for block in blocks:
        text = _normalize_ws(block.text)
        if not text:
            continue
        if len(text) > cfg.max_chars:
            flush()
            for part in _split_text(text, cfg.max_chars, cfg.overlap_chars):
                split_block = DocumentBlock(
                    text=part,
                    source_file=block.source_file,
                    block_type=block.block_type,
                    locator=block.locator,
                    heading_path=block.heading_path,
                    metadata=block.metadata,
                )
                _append_chunk(chunks, doc_id, [split_block], part)
            continue
        candidate = f"{buffer_text}\n\n{text}".strip() if buffer_text else text
        if buffer and len(candidate) > cfg.max_chars:
            flush()
            overlap = _tail(buffer_text, cfg.overlap_chars)
            buffer = [block]
            buffer_text = f"{overlap}\n\n{text}".strip() if overlap else text
        else:
            buffer.append(block)
            buffer_text = candidate

    flush()
    return _link_chunks(chunks)


def _append_chunk(chunks: list[Chunk], doc_id: str, blocks: list[DocumentBlock], text: str) -> None:
    first = blocks[0]
    chunk_id = f"{doc_id}:{len(chunks) + 1:04d}"
    block_types = []
    for block in blocks:
        if block.block_type not in block_types:
            block_types.append(block.block_type)
    chunks.append(
        Chunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=text,
            source_file=first.source_file,
            locator=first.locator,
            heading_path=first.heading_path,
            prev_chunk_id=None,
            next_chunk_id=None,
            metadata={"block_types": block_types, "block_count": len(blocks)},
        )
    )


def _link_chunks(chunks: list[Chunk]) -> list[Chunk]:
    linked: list[Chunk] = []
    for i, chunk in enumerate(chunks):
        linked.append(
            Chunk(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                text=chunk.text,
                source_file=chunk.source_file,
                locator=chunk.locator,
                heading_path=chunk.heading_path,
                prev_chunk_id=chunks[i - 1].chunk_id if i > 0 else None,
                next_chunk_id=chunks[i + 1].chunk_id if i + 1 < len(chunks) else None,
                metadata=chunk.metadata,
            )
        )
    return linked


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_hard_split(sentence, max_chars, overlap_chars))
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > max_chars:
            parts.append(current)
            overlap = _tail(current, overlap_chars)
            current = f"{overlap} {sentence}".strip() if overlap else sentence
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        parts.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap_chars)
    return [part for part in parts if part]


def _tail(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text if max_chars > 0 else ""
    tail = text[-max_chars:]
    first_space = tail.find(" ")
    return tail[first_space + 1 :].strip() if first_space >= 0 else tail.strip()


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
