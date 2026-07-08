from __future__ import annotations

from doc_chunker.chunker import ChunkingConfig, chunk_blocks
from doc_chunker.models import DocumentBlock


def test_chunk_blocks_preserve_heading_metadata_and_links() -> None:
    blocks = [
        DocumentBlock(
            text="alpha beta gamma",
            source_file="guide.docx",
            block_type="paragraph",
            locator={"paragraph": 1},
            heading_path=["Intro"],
        ),
        DocumentBlock(
            text="delta epsilon zeta",
            source_file="guide.docx",
            block_type="paragraph",
            locator={"paragraph": 2},
            heading_path=["Intro"],
        ),
    ]

    chunks = chunk_blocks(blocks, doc_id="doc-1", config=ChunkingConfig(max_chars=80, overlap_chars=10))

    assert len(chunks) == 1
    assert chunks[0].doc_id == "doc-1"
    assert chunks[0].source_file == "guide.docx"
    assert chunks[0].heading_path == ["Intro"]
    assert chunks[0].prev_chunk_id is None
    assert chunks[0].next_chunk_id is None
    assert chunks[0].metadata["block_types"] == ["paragraph"]


def test_chunk_blocks_split_long_text_on_sentence_boundary_with_overlap() -> None:
    blocks = [
        DocumentBlock(
            text=(
                "Sentence one has useful context. "
                "Sentence two should stay whole. "
                "Sentence three should move into another chunk."
            ),
            source_file="notes.txt",
            block_type="paragraph",
            locator={"line": 1},
            heading_path=[],
        )
    ]

    chunks = chunk_blocks(blocks, doc_id="doc-2", config=ChunkingConfig(max_chars=62, overlap_chars=20))

    assert len(chunks) >= 2
    assert all(len(chunk.text) <= 82 for chunk in chunks)
    assert chunks[0].next_chunk_id == chunks[1].chunk_id
    assert chunks[1].prev_chunk_id == chunks[0].chunk_id
    assert "Sentence two should stay whole." in chunks[1].text


def test_chunk_blocks_never_splits_mid_sentence() -> None:
    """Invariant: every non-hard-split chunk boundary falls on a sentence
    end (a run of sentence-final punctuation), for both English and
    unspaced Chinese punctuation. Regression guard for REVIEW_FINDINGS.md
    C6 (Chinese sentence splitter silently no-op'd without a following
    space)."""
    text = (
        "这是第一句用来测试中文分句的效果。这是第二句同样需要被正确切分。"
        "这是第三句继续增加长度以触发切分逻辑。这是第四句确保超过配置的字符上限。"
    )
    blocks = [
        DocumentBlock(
            text=text,
            source_file="zh.txt",
            block_type="paragraph",
            locator={"line": 1},
        )
    ]

    chunks = chunk_blocks(blocks, doc_id="zh-doc", config=ChunkingConfig(max_chars=40, overlap_chars=5))

    assert len(chunks) >= 2
    sentence_enders = "。！？.!?"
    for chunk in chunks:
        stripped = chunk.text.strip()
        assert stripped[-1] in sentence_enders, f"chunk ends mid-sentence: {stripped!r}"
    rejoined = "".join(chunk.text for chunk in chunks)
    assert "第三句继续增加长度以触发切分逻辑。" in rejoined


def test_split_text_does_not_break_decimal_numbers() -> None:
    """Regression: the sentence splitter treated the '.' in a decimal
    number as a sentence end, corrupting "3.2x" into two chunks
    ("3." / "2x")."""
    text = (
        "Baseline throughput was measured at 1.5 requests per second. "
        "Peak capacity is projected to reach 3.2x normal traffic, which the team called acceptable."
    )
    blocks = [
        DocumentBlock(text=text, source_file="notes.txt", block_type="paragraph", locator={"line": 1})
    ]

    chunks = chunk_blocks(blocks, doc_id="doc-dec", config=ChunkingConfig(max_chars=60, overlap_chars=0))

    rejoined = " ".join(chunk.text for chunk in chunks)
    assert "3.2x" in rejoined
    assert "1.5 requests" in rejoined


def test_chunk_blocks_does_not_cross_heading_boundary() -> None:
    """Merging two short blocks from different sections must not mislabel
    the second section's content as belonging to the first (REVIEW_FINDINGS
    C7): each output chunk's heading_path must match every block folded
    into it."""
    blocks = [
        DocumentBlock(
            text="Tail of section A.",
            source_file="doc.docx",
            block_type="paragraph",
            locator={"paragraph": 1},
            heading_path=["Section A"],
        ),
        DocumentBlock(
            text="Start of section B.",
            source_file="doc.docx",
            block_type="paragraph",
            locator={"paragraph": 2},
            heading_path=["Section B"],
        ),
    ]

    chunks = chunk_blocks(blocks, doc_id="doc-x", config=ChunkingConfig(max_chars=200, overlap_chars=10))

    assert len(chunks) == 2
    assert chunks[0].heading_path == ["Section A"]
    assert "Section A" in chunks[0].text or "Tail of section A" in chunks[0].text
    assert chunks[1].heading_path == ["Section B"]
    assert "Start of section B" in chunks[1].text
    assert "Start of section B" not in chunks[0].text


def test_chunk_blocks_does_not_cross_block_type_boundary() -> None:
    blocks = [
        DocumentBlock(
            text="A short paragraph.",
            source_file="doc.docx",
            block_type="paragraph",
            locator={"paragraph": 1},
        ),
        DocumentBlock(
            text="Risk: Parser drift; Owner: Candidate",
            source_file="doc.docx",
            block_type="table_row",
            locator={"row": 1},
        ),
    ]

    chunks = chunk_blocks(blocks, doc_id="doc-y", config=ChunkingConfig(max_chars=200, overlap_chars=10))

    assert len(chunks) == 2
    assert chunks[0].metadata["block_types"] == ["paragraph"]
    assert chunks[1].metadata["block_types"] == ["table_row"]


def test_chunk_metadata_merges_first_block_metadata() -> None:
    """D006/H2: structured metadata captured by the parser (e.g. table
    headers) must survive into the stored chunk, not just the chunk text."""
    blocks = [
        DocumentBlock(
            text="Risk: Parser drift; Owner: Candidate",
            source_file="sample.xlsx",
            block_type="table_row",
            locator={"sheet": "Risks", "row": 2},
            heading_path=["Risks"],
            metadata={"headers": ["Risk", "Owner"]},
        )
    ]

    chunks = chunk_blocks(blocks, doc_id="doc-z", config=ChunkingConfig(max_chars=200, overlap_chars=10))

    assert chunks[0].metadata["headers"] == ["Risk", "Owner"]
    assert chunks[0].metadata["block_types"] == ["table_row"]


def test_all_chunks_concatenated_without_overlap_reconstructs_source() -> None:
    # No whitespace anywhere in the source, so the hard-splitter's
    # boundary .strip() calls are no-ops and concatenation is exact --
    # isolates the "no data lost across a hard split" invariant from
    # word-boundary/whitespace concerns, which sentence-aware splitting
    # already covers in the tests above.
    text = "abcdefghij" * 12
    blocks = [
        DocumentBlock(text=text, source_file="notes.txt", block_type="paragraph", locator={"line": 1})
    ]

    chunks = chunk_blocks(blocks, doc_id="doc-r", config=ChunkingConfig(max_chars=40, overlap_chars=0))

    assert len(chunks) >= 2
    rejoined = "".join(chunk.text for chunk in chunks)
    assert rejoined == text


def test_chunking_config_rejects_invalid_overlap() -> None:
    import pytest

    with pytest.raises(ValueError):
        ChunkingConfig(max_chars=100, overlap_chars=100)


def test_empty_blocks_produce_no_chunks() -> None:
    assert chunk_blocks([], doc_id="doc-empty") == []
    blank = [DocumentBlock(text="   ", source_file="x.txt", block_type="paragraph", locator={})]
    assert chunk_blocks(blank, doc_id="doc-blank") == []


def test_same_input_same_config_is_deterministic() -> None:
    blocks = [
        DocumentBlock(
            text="Repeatable input text that should chunk the same way every run.",
            source_file="notes.txt",
            block_type="paragraph",
            locator={"line": 1},
        )
    ]
    config = ChunkingConfig(max_chars=40, overlap_chars=5)
    first = chunk_blocks(blocks, doc_id="doc-det", config=config)
    second = chunk_blocks(blocks, doc_id="doc-det", config=config)
    assert [c.text for c in first] == [c.text for c in second]
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
