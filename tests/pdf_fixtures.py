"""Hand-built minimal PDF fixtures for parser tests.

The previous PDF test used `pytest.importorskip("fitz")` (PyMuPDF) to
generate a throwaway test PDF, but PyMuPDF is not a declared dependency of
this package (see pyproject.toml). In a clean install, `fitz` is missing,
`importorskip` skips the test silently, and `parse_pdf()` -- the actual
pypdf-based code path users hit -- never runs in CI. See
docs/process/REVIEW_FINDINGS.md H1.

These helpers write raw PDF 1.4 bytes directly (one text run via the
built-in Helvetica base font, no embedded font needed) so the fixtures have
zero extra dependencies beyond pypdf, which the package already requires.
"""

from __future__ import annotations

from pathlib import Path


def _pdf_object_bytes(index: int, body: bytes) -> bytes:
    return f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n"


def build_minimal_pdf_bytes(text: str, *, y: int = 700) -> bytes:
    """Build a single-page PDF whose content stream draws `text`."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        None,  # filled below once the content stream is built
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = f"BT /F1 18 Tf 72 {y} Td ({_escape(text)}) Tj ET".encode("latin-1")
    objects[3] = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += _pdf_object_bytes(i, body)

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += b"trailer\n"
    out += f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
    out += b"startxref\n"
    out += f"{xref_offset}\n".encode("ascii")
    out += b"%%EOF"
    return bytes(out)


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def write_minimal_pdf(path: Path, text: str) -> None:
    path.write_bytes(build_minimal_pdf_bytes(text))


def write_outline_pdf(path: Path, sections: list[tuple[str, str]]) -> None:
    """Write a multi-page PDF, one page per (heading_title, body_text) pair,
    with a top-level outline/bookmark entry per page. Uses pypdf's
    PdfWriter to assemble pages and outline entries -- pypdf is already a
    required runtime dependency of this package, so this adds no new test
    dependency."""
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for _, body in sections:
        reader = PdfReader(_bytes_io(build_minimal_pdf_bytes(body)))
        writer.add_page(reader.pages[0])
    for page_index, (title, _) in enumerate(sections):
        writer.add_outline_item(title, page_index)
    with path.open("wb") as handle:
        writer.write(handle)


def _bytes_io(data: bytes):
    import io

    return io.BytesIO(data)
