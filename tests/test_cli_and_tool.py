from __future__ import annotations

import asyncio
import json
from pathlib import Path

from doc_chunker.cli import main
from doc_chunker.nanobot_tool import DocumentChunkerTool


def test_cli_ingest_and_search(tmp_path: Path, capsys) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Alpha topic.\n\nBeta topic has search value.", encoding="utf-8")
    index = tmp_path / "index"

    assert main(["ingest", str(source), "--out", str(index), "--max-chars", "80"]) == 0
    ingest_output = json.loads(capsys.readouterr().out)
    assert ingest_output["chunk_count"] >= 1

    assert main(["search", str(index), "search value"]) == 0
    search_output = json.loads(capsys.readouterr().out)
    assert search_output["matches"][0]["source_file"] == str(source)


def test_nanobot_tool_schema_and_execute_ingest_search(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Needle appears in this document.", encoding="utf-8")
    index = tmp_path / "index"
    tool = DocumentChunkerTool()

    assert tool.name == "document_chunker"
    assert tool.parameters["required"] == ["action", "store_dir"]

    ingest = asyncio.run(tool.execute(action="ingest", store_dir=str(index), path=str(source)))
    ingest_payload = json.loads(str(ingest))
    assert ingest_payload["ok"] is True
    assert ingest_payload["chunk_count"] == 1

    search = asyncio.run(tool.execute(action="search", store_dir=str(index), query="Needle"))
    search_payload = json.loads(str(search))
    assert search_payload["ok"] is True
    assert search_payload["matches"][0]["chunk_id"].endswith(":0001")
