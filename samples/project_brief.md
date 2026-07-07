# Doc Chunker Project Brief

## Goal

The document_chunker tool converts local documents into searchable chunks for a nanobot agent. The first version focuses on parser boundaries, chunk metadata, and a simple local index.

## Module Boundary

The parser layer reads files and emits DocumentBlock objects. The chunker layer receives those blocks and emits Chunk objects. The store layer writes manifest.json and chunks.jsonl so the result can be inspected without a database.

## Integration

The CLI path is useful for module-level validation. The nanobot Tool path is useful for system-level validation because ToolLoader discovers the document_chunker entry point and ToolRegistry executes the tool.

## Upgrade Notes

Future versions could replace keyword search with BM25, SQLite FTS, or vector search. The parser could also be replaced by Docling or Unstructured while keeping the same DocumentBlock contract.
