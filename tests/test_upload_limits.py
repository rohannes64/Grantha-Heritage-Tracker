"""Upload safety: oversized pages, decompression bombs, oversized requests, and service errors."""
import io

import pytest
from PIL import Image

from app import ocr_input


def test_huge_image_is_refused_not_decoded(monkeypatch):
    monkeypatch.setattr(ocr_input, "MAX_PIXELS", 1_000_000)
    buf = io.BytesIO()
    Image.new("L", (2000, 2000), 255).save(buf, format="PNG")     # 4 MP > 1 MP limit
    with pytest.raises(ocr_input.OCRInputError, match="too large"):
        ocr_input.images_from_upload(buf.getvalue(), "page.png")


def test_pdf_pages_are_rendered_within_the_pixel_cap(monkeypatch):
    fitz = pytest.importorskip("fitz")
    monkeypatch.setattr(ocr_input, "MAX_PIXELS", 2_000_000)
    doc = fitz.open()
    for _ in range(ocr_input.MAX_PAGES + 3):
        doc.new_page(width=5000, height=5000)            # a page declaring ~69 x 69 inches
    pages = ocr_input.images_from_upload(doc.tobytes(), "big.pdf")
    assert len(pages) == ocr_input.MAX_PAGES
    assert all(p.width * p.height <= 2_000_000 for p in pages)


def test_request_body_over_the_limit_is_refused_early(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "MAX_UPLOAD", 1000)
    client = TestClient(main.app)
    r = client.post("/api/check", files={"file": ("x.png", b"0" * 50_000, "image/png")})
    assert r.status_code == 413


def test_service_error_message_names_no_vendor_and_hides_details(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from pipeline.features import EmbeddingServiceError

    class Down:
        b = {"feature_set": "V"}

        def check_text(self, *a, **k):
            raise EmbeddingServiceError("Vertex AI answered HTTP 403: {internal project details}")

    monkeypatch.setattr(main, "checker", lambda: Down())
    r = TestClient(main.app).post("/api/check", data={"text": "word " * 50, "lang": "eng"})
    assert r.status_code == 503
    assert "internal project details" not in r.text and "Gemini" not in r.text
