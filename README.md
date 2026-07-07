# doc-chunker

Context-aware document parsing and chunking module for the Lenovo AI Coding take-home.

The first version keeps the scope intentionally small: parse local documents, convert them to normalized blocks, create linked chunks with context metadata, store them in local JSONL, and expose the flow through both a CLI and a nanobot Tool adapter.

## Documentation Map

- `DESIGN.md`: architecture, data flow, boundaries, and known limits.
- `DECISIONS.md`: design decisions and trade-offs.
- `TESTING.md`: automated tests and manual demo commands.
- `docs/study/`: beginner guide and study path.
- `docs/interview/`: interview script and checklist.
- `docs/process/`: AI workflow notes and review findings.

## Quickstart

Run tests:

```bash
python -m pytest tests -q
```

Ingest a document:

```bash
python -m doc_chunker.cli ingest samples/example.docx --out .doc_index
```

Search an index:

```bash
python -m doc_chunker.cli search .doc_index "keyword"
```

When running from the repo without installation, set `PYTHONPATH=src` or run tests, which already inject `src`.

## Supported Inputs

- `.pdf`: text extraction by page through `pypdf`.
- `.docx`: paragraphs and heading styles extracted from the Word XML package.
- `.xlsx`: rows extracted by sheet through `openpyxl`; the first row is treated as headers.
- `.txt`, `.md`, `.csv`: included as low-cost demo and testing formats.

## Output Format

Each store directory contains:

- `manifest.json`: document ID, source path, parser, chunk count, chunking config, and timestamps.
- `chunks.jsonl`: one JSON object per chunk.

Chunk fields include `chunk_id`, `doc_id`, `text`, `source_file`, `locator`, `heading_path`, `prev_chunk_id`, `next_chunk_id`, and `metadata`.

## Nanobot Integration

`pyproject.toml` declares:

```toml
[project.entry-points."nanobot.tools"]
document_chunker = "doc_chunker.nanobot_tool:DocumentChunkerTool"
```

The adapter exposes one tool named `document_chunker` with two actions:

- `ingest`: parse and store chunks from a local path.
- `search`: return matching chunks from an existing store.

The core package does not import nanobot except inside `nanobot_tool.py`, so parsing, chunking, and storage remain independently testable.
