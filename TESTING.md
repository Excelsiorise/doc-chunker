# Testing

## Automated Tests

Run:

```bash
python -m pytest tests -q
```

In this sandboxed workspace, pytest needs a writable temp directory inside the project:

```powershell
New-Item -ItemType Directory -Force -Path .tmp | Out-Null
$env:PYTHONPATH="src"
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
python -m pytest tests -q
```

Latest verified result on 2026-07-06:

```text
9 passed in 0.61s
```

Current coverage focus:

- `tests/test_chunker.py`: verifies heading metadata, chunk size behavior, overlap, and prev/next links.
- `tests/test_parsers.py`: verifies DOCX heading/paragraph extraction, XLSX sheet row extraction, and PDF page text extraction.
- `tests/test_store.py`: verifies JSONL round trip, manifest writing, and keyword search.
- `tests/test_cli_and_tool.py`: verifies CLI ingest/search and nanobot Tool schema/execution contract.

## Manual Demo Commands

From `doc-chunker/`, use:

```bash
python -m doc_chunker.cli ingest path\to\document.docx --out .doc_index
python -m doc_chunker.cli search .doc_index "keyword"
```

If the package is not installed, set:

```bash
$env:PYTHONPATH="src"
```

Latest demo command:

```powershell
$env:PYTHONPATH="src"
python -m doc_chunker.cli ingest samples\example.txt --out .doc_index --max-chars 160 --overlap-chars 20
python -m doc_chunker.cli search .doc_index "chunker validation"
```

Observed result:

```text
ingest returned ok=true, doc_id=example-9629550649, chunk_count=2
search returned ok=true with linked chunks containing prev_chunk_id/next_chunk_id metadata
```

## Validation Methodology

The tests check behavior at module boundaries rather than private implementation details:

- Parser tests assert normalized `DocumentBlock` outputs.
- Chunker tests assert externally useful chunk metadata.
- Store tests assert persisted files can be read back.
- Tool tests assert nanobot-facing schema and async execution behavior.

This matters for AI-assisted coding: a test that only mirrors implementation would not catch a wrong design. These tests encode the assignment requirements directly.
