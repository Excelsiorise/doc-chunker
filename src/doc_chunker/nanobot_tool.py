from __future__ import annotations

import json
from typing import Any

from doc_chunker.pipeline import ingest_document
from doc_chunker.store import DocumentStore

try:
    from nanobot.agent.tools.base import Tool, ToolResult
except Exception:  # pragma: no cover - lets core package import outside nanobot envs
    class Tool:  # type: ignore[no-redef]
        pass

    class ToolResult(str):  # type: ignore[no-redef]
        @classmethod
        def error(cls, content: str) -> "ToolResult":
            return cls(content)


class DocumentChunkerTool(Tool):
    @property
    def name(self) -> str:
        return "document_chunker"

    @property
    def description(self) -> str:
        return "Parse documents, create context-aware chunks, store them locally, and search stored chunks."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["ingest", "search"]},
                "store_dir": {"type": "string", "description": "Directory containing manifest.json and chunks.jsonl."},
                "path": {"type": "string", "description": "Document path for ingest."},
                "query": {"type": "string", "description": "Keyword query for search."},
                "max_chars": {"type": "integer", "minimum": 80, "default": 1000},
                "overlap_chars": {"type": "integer", "minimum": 0, "default": 150},
                "limit": {"type": "integer", "minimum": 1, "default": 5},
            },
            "required": ["action", "store_dir"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> Any:
        action = kwargs.get("action")
        store_dir = kwargs.get("store_dir")
        try:
            if action == "ingest":
                path = kwargs.get("path")
                if not path:
                    return ToolResult.error("path is required for action=ingest")
                payload = ingest_document(
                    path,
                    store_dir=store_dir,
                    max_chars=int(kwargs.get("max_chars") or 1000),
                    overlap_chars=int(kwargs.get("overlap_chars") or 150),
                )
            elif action == "search":
                query = kwargs.get("query")
                if not query:
                    return ToolResult.error("query is required for action=search")
                payload = {
                    "ok": True,
                    "matches": DocumentStore(store_dir).search(
                        str(query),
                        limit=int(kwargs.get("limit") or 5),
                    ),
                }
            else:
                return ToolResult.error(f"Unsupported action: {action}")
        except Exception as exc:
            return ToolResult.error(str(exc))
        return json.dumps(payload, ensure_ascii=False, indent=2)
