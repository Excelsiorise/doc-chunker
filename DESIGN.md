# Design

## Goal

Build a small, runnable document import and chunking module that demonstrates context-aware chunk boundaries and a clear integration path with nanobot. The module is not a full RAG platform: it deliberately avoids vector databases, embedding training, and a separate MCP server in the first version.

## Architecture

The implementation has five layers:

1. `parsers.py` reads source files and returns normalized `DocumentBlock` records.
2. `chunker.py` turns blocks into linked `Chunk` records with heading and locator metadata.
3. `store.py` persists chunks to `chunks.jsonl` and writes `manifest.json`.
4. `cli.py` exposes ingest/search for local demos and verification.
5. `nanobot_tool.py` adapts the same core behavior to nanobot's `Tool` interface.

The core layers do not depend on nanobot. This keeps the design easy to test and allows the same module to be reused outside nanobot.

## Data Flow

```text
PDF/DOCX/XLSX path
  -> parse_document()
  -> list[DocumentBlock]
  -> chunk_blocks()
  -> list[Chunk]
  -> DocumentStore.write_document()
  -> manifest.json + chunks.jsonl
```

Search is intentionally deterministic in version one:

```text
query -> DocumentStore.search() -> matching chunk dictionaries
```

This is enough to show how downstream retrieval/generation would receive grounded snippets without adding an embedding dependency.

## Context-Aware Chunking

The chunker preserves context in three ways:

- `heading_path` records the section or sheet context.
- `locator` records page, paragraph, row, or sheet position.
- `prev_chunk_id` and `next_chunk_id` preserve neighboring chunk relationships.

The splitter prefers sentence boundaries when a block is larger than `max_chars`, and adds configurable overlap between split chunks.

## Parser Choices

- DOCX parsing uses the Word XML package directly. This avoids a hard runtime dependency on `python-docx` while still extracting headings and paragraphs.
- XLSX parsing uses `openpyxl`, which is already a practical dependency for Excel.
- PDF parsing uses `pypdf`, matching nanobot's own optional document dependency family.

## Storage Choice

Version one uses JSONL plus a manifest instead of SQLite. JSONL is easy to inspect in an interview, easy to diff, and simple to validate with tests. SQLite is a reasonable future improvement if ranking, filtering, or larger indexes become important.

## Nanobot Boundary

The nanobot adapter is intentionally thin. It owns only:

- tool name and description;
- JSON schema parameters;
- `ingest` and `search` dispatch;
- conversion of exceptions into `ToolResult.error(...)`.

All meaningful parsing, chunking, and storage behavior remains in the standalone package.

## Known Limits

- Search is keyword matching, not semantic retrieval.
- DOCX heading extraction handles common `Heading1`, `Heading2` style names but not every localized Word style.
- PDF quality depends on extractable text; scanned PDFs need OCR, which is out of scope.
- The store overwrites chunks for the same document ID and appends chunks from different documents.

## One-Week Extension Plan

Given more time, the next steps would be:

1. Add SQLite as an optional store backend with document/chunk tables.
2. Add BM25 or embedding-backed retrieval while keeping JSONL as a debug export.
3. Add richer table chunking for merged cells and multi-row headers.
4. Add a nanobot Skill that teaches the agent when to call `document_chunker`.
5. Add an optional MCP server adapter over the same core package.
