from app.services.extraction_service import extract_text

def test_extract_txt():
    text = extract_text(b"hello world", "txt")
    assert text == "hello world"

def test_extract_csv():
    text = extract_text(b"a,b,c\n1,2,3", "csv")
    assert "a,b,c" in text

def test_extract_image_placeholder():
    text = extract_text(b"\x89PNG", "png")
    assert "Image file" in text  # Placeholder message for sync extraction

def test_extract_unknown():
    text = extract_text(b"data", "xyz")
    assert "Unsupported" in text
