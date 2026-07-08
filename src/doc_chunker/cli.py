from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from doc_chunker.pipeline import ingest_document
from doc_chunker.store import DocumentStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="doc-chunker")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Parse, chunk, and store one document.")
    ingest.add_argument("path")
    ingest.add_argument("--out", required=True, dest="store_dir")
    ingest.add_argument("--max-chars", type=int, default=1000)
    ingest.add_argument("--overlap-chars", type=int, default=150)

    search = sub.add_parser("search", help="Search a local chunk store.")
    search.add_argument("store_dir")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument(
        "--expand",
        choices=["neighbors", "section"],
        default=None,
        help="Restore context around each hit: 'neighbors' (prev/next window) "
        "or 'section' (all chunks sharing the hit's heading_path).",
    )

    export = sub.add_parser("export", help="Export one document's chunks to a file.")
    export.add_argument("store_dir")
    export.add_argument("--doc-id", required=True)
    export.add_argument("--out", required=True, dest="out_path")
    export.add_argument("--format", choices=["jsonl", "json"], default="jsonl")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            payload = ingest_document(
                args.path,
                store_dir=args.store_dir,
                max_chars=args.max_chars,
                overlap_chars=args.overlap_chars,
            )
        elif args.command == "search":
            payload = {
                "ok": True,
                "matches": DocumentStore(args.store_dir).search(
                    args.query, limit=args.limit, expand=args.expand
                ),
            }
        elif args.command == "export":
            payload = _export(args)
        else:  # pragma: no cover - argparse prevents this
            parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _export(args: argparse.Namespace) -> dict[str, object]:
    store = DocumentStore(args.store_dir)
    chunks = store.get_by_document(args.doc_id)
    if not chunks:
        return {"ok": False, "error": f"no chunks found for doc_id={args.doc_id!r}"}
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "jsonl":
        with out_path.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
    else:
        out_path.write_text(
            json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {"ok": True, "doc_id": args.doc_id, "chunk_count": len(chunks), "out": str(out_path)}


def console_main() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    console_main()
