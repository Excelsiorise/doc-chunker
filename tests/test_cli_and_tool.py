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

    assert main(["ingest", str(source), "--out", str(index), "--max-chars", "80", "--overlap-chars", "10"]) == 0
    ingest_output = json.loads(capsys.readouterr().out)
    assert ingest_output["chunk_count"] >= 1

    assert main(["search", str(index), "search value"]) == 0
    search_output = json.loads(capsys.readouterr().out)
    assert search_output["matches"][0]["source_file"] == str(source)


def test_cli_search_expand_and_export(tmp_path: Path, capsys) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Alpha topic.\n\nBeta topic has search value.", encoding="utf-8")
    index = tmp_path / "index"

    assert main(["ingest", str(source), "--out", str(index), "--max-chars", "80", "--overlap-chars", "10"]) == 0
    ingest_output = json.loads(capsys.readouterr().out)
    doc_id = ingest_output["doc_id"]

    assert main(["search", str(index), "search value", "--expand", "neighbors"]) == 0
    search_output = json.loads(capsys.readouterr().out)
    assert "context" in search_output["matches"][0]

    export_path = tmp_path / "export.jsonl"
    assert main(["export", str(index), "--doc-id", doc_id, "--out", str(export_path)]) == 0
    export_output = json.loads(capsys.readouterr().out)
    assert export_output["ok"] is True
    assert export_output["chunk_count"] >= 1
    assert export_path.exists()
    lines = export_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == export_output["chunk_count"]


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


def test_nanobot_tool_expand_param_returns_context(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Needle appears in this document.", encoding="utf-8")
    index = tmp_path / "index"
    tool = DocumentChunkerTool()

    asyncio.run(tool.execute(action="ingest", store_dir=str(index), path=str(source)))
    search = asyncio.run(
        tool.execute(action="search", store_dir=str(index), query="Needle", expand="neighbors")
    )
    payload = json.loads(str(search))

    assert payload["matches"][0]["expand"] == "neighbors"
    assert "context" in payload["matches"][0]
