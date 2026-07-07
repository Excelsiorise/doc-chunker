# Doc Chunker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable document parsing, context-aware chunking, local storage, CLI, and nanobot Tool adapter module for the take-home assignment.

**Architecture:** Keep the core `doc_chunker` package independent from nanobot. Parse files into normalized `DocumentBlock` records, chunk those records into linked `Chunk` records, persist them as JSONL plus a manifest, then expose the same ingest/search behavior through CLI and a thin nanobot Tool plugin.

**Tech Stack:** Python 3.11+, pytest, stdlib zip/xml/csv/json/pathlib, optional `pypdf` for PDF and `openpyxl` for Excel, nanobot Tool ABC for adapter tests.

---

### Task 1: Core Data Model And Chunker

**Files:**
- Create: `doc-chunker/src/doc_chunker/models.py`
- Create: `doc-chunker/src/doc_chunker/chunker.py`
- Test: `doc-chunker/tests/test_chunker.py`

- [ ] Write tests for chunk size limits, heading metadata, and prev/next links.
- [ ] Run the tests and confirm they fail because the package does not exist.
- [ ] Implement dataclasses and chunking logic with configurable `max_chars` and `overlap_chars`.
- [ ] Run the tests and confirm they pass.

### Task 2: Parsers

**Files:**
- Create: `doc-chunker/src/doc_chunker/parsers.py`
- Test: `doc-chunker/tests/test_parsers.py`

- [ ] Write tests using generated DOCX/XLSX/PDF fixtures where possible.
- [ ] Run parser tests and confirm they fail before implementation.
- [ ] Implement plain text, DOCX, XLSX, and PDF parsers that return `DocumentBlock` records.
- [ ] Run parser tests and confirm they pass.

### Task 3: Store And Search

**Files:**
- Create: `doc-chunker/src/doc_chunker/store.py`
- Test: `doc-chunker/tests/test_store.py`

- [ ] Write tests for JSONL round trip, manifest content, and simple keyword search.
- [ ] Run store tests and confirm they fail before implementation.
- [ ] Implement `DocumentStore` with `manifest.json` and `chunks.jsonl`.
- [ ] Run store tests and confirm they pass.

### Task 4: CLI And Nanobot Tool Adapter

**Files:**
- Create: `doc-chunker/src/doc_chunker/cli.py`
- Create: `doc-chunker/src/doc_chunker/nanobot_tool.py`
- Create: `doc-chunker/pyproject.toml`
- Test: `doc-chunker/tests/test_cli_and_tool.py`

- [ ] Write tests for CLI ingest/search and nanobot tool schema/execution contract.
- [ ] Run tests and confirm they fail before implementation.
- [ ] Implement CLI subcommands and `DocumentChunkerTool`.
- [ ] Run tests and confirm they pass.

### Task 5: Documentation And Verification

**Files:**
- Create: `doc-chunker/README.md`
- Create: `doc-chunker/DESIGN.md`
- Create: `doc-chunker/TESTING.md`
- Modify: `doc-chunker/AI_WORKFLOW.md`

- [ ] Document quickstart, architecture, decisions, tests, and known limits.
- [ ] Run `pytest`.
- [ ] Run `python -m doc_chunker.cli --help`.
- [ ] Run a small ingest/search demo.
- [ ] Record verification evidence in `TESTING.md` and `AI_WORKFLOW.md`.
