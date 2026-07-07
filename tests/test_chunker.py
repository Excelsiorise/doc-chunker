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
