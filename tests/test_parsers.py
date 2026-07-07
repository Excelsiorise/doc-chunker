from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook
import pytest

from doc_chunker.parsers import parse_document


def _write_minimal_docx(path: Path) -> None:
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>Project Overview</w:t></w:r>
    </w:p>
    <w:p><w:r><w:t>First paragraph from docx.</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
    with ZipFile(path, "w", ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", document_xml)


def test_parse_docx_extracts_headings_and_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    _write_minimal_docx(path)

    blocks = parse_document(path)

    assert [block.text for block in blocks] == ["Project Overview", "First paragraph from docx."]
    assert blocks[0].block_type == "heading"
    assert blocks[1].heading_path == ["Project Overview"]


def test_parse_xlsx_extracts_sheet_rows_with_header_metadata(tmp_path: Path) -> None:
    path = tmp_path / "sample.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Risks"
    ws.append(["Risk", "Owner"])
    ws.append(["Parser drift", "Candidate"])
    wb.save(path)

    blocks = parse_document(path)

    assert len(blocks) == 1
    assert blocks[0].block_type == "table_row"
    assert blocks[0].locator == {"sheet": "Risks", "row": 2}
    assert blocks[0].metadata["headers"] == ["Risk", "Owner"]
    assert "Parser drift" in blocks[0].text


def test_parse_pdf_extracts_page_text(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF page text for chunking.")
    doc.save(path)
    doc.close()

    blocks = parse_document(path)

    assert len(blocks) == 1
    assert blocks[0].block_type == "page"
    assert blocks[0].locator == {"page": 1}
    assert "PDF page text" in blocks[0].text
