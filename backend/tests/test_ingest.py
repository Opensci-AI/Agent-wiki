from app.services.ingest_service import parse_file_blocks, parse_review_blocks


def test_parse_file_blocks():
    text = (
        "---FILE: wiki/entities/ml.md---\n"
        "# ML\nContent\n"
        "---END FILE---\n\n"
        "---FILE: wiki/concepts/nn.md---\n"
        "# NN\n"
        "---END FILE---"
    )
    blocks = parse_file_blocks(text)
    assert len(blocks) == 2
    assert "ml.md" in blocks[0][0]


def test_parse_review_blocks():
    text = (
        "---REVIEW: contradiction | Conflict---\n"
        "Desc\n"
        "OPTIONS: Create Page | Skip\n"
        "PAGES: wiki/a.md\n"
        "SEARCH: q1 | q2\n"
        "---END REVIEW---"
    )
    reviews = parse_review_blocks(text, "src.pdf")
    assert len(reviews) == 1
    assert reviews[0]["type"] == "contradiction"
    assert len(reviews[0]["search_queries"]) == 2


def test_parse_empty():
    assert parse_file_blocks("no blocks") == []
    assert parse_review_blocks("no reviews") == []
