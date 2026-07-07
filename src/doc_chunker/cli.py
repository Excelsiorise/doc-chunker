from __future__ import annotations

import argparse
import json
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
                "matches": DocumentStore(args.store_dir).search(args.query, limit=args.limit),
            }
        else:  # pragma: no cover - argparse prevents this
            parser.error(f"Unknown command: {args.command}")
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def console_main() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    console_main()
