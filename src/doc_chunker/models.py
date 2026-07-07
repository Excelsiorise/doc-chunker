from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class DocumentBlock:
    text: str
    source_file: str
    block_type: str
    locator: dict[str, Any]
    heading_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    source_file: str
    locator: dict[str, Any]
    heading_path: list[str]
    prev_chunk_id: str | None
    next_chunk_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chunk:
        return cls(
            chunk_id=str(data["chunk_id"]),
            doc_id=str(data["doc_id"]),
            text=str(data["text"]),
            source_file=str(data["source_file"]),
            locator=dict(data.get("locator") or {}),
            heading_path=list(data.get("heading_path") or []),
            prev_chunk_id=data.get("prev_chunk_id"),
            next_chunk_id=data.get("next_chunk_id"),
            metadata=dict(data.get("metadata") or {}),
        )
