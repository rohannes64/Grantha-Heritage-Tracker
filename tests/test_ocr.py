import shutil

import pytest

from pipeline import ocr


def test_script_ratio():
    assert ocr.script_ratio("hello world", "Latin") == 1.0
    assert ocr.script_ratio("नमस्ते", "Devanagari") == 1.0
    assert ocr.script_ratio("नमस्ते abc", "Devanagari") < 1.0
    assert ocr.script_ratio("123 ,,", "Latin") is None


def test_choose_model_trusts_tag_only_when_script_agrees():
    assert ocr.choose_model("san", ["Devanagari", "Devanagari"]) == ("san", "Devanagari")
    assert ocr.choose_model("san", ["Latin", "Latin", "Devanagari"]) == ("eng", "Latin")
    assert ocr.choose_model("tam", []) == ("tam", "Tamil")


needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")


@needs_tesseract
def test_installed_languages():
    import pytesseract
    have = set(pytesseract.get_languages())
    assert {"eng", "hin", "san", "ben", "guj", "tel", "kan", "tam", "osd"} <= have


def _render(text: str):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("DejaVuSans.ttf", 34) if _has_dejavu() else ImageFont.load_default(size=34)
    img = Image.new("L", (1200, 900), 255)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(text.split("\n")):
        d.text((60, 60 + i * 50), line, fill=0, font=font)
    return img


def _has_dejavu():
    from PIL import ImageFont
    try:
        ImageFont.truetype("DejaVuSans.ttf", 10)
        return True
    except OSError:
        return False


@needs_tesseract
@pytest.mark.parametrize("turn", [0, 90, 180, 270])
def test_rotation_fix_reads_rotated_page(tmp_path, monkeypatch, turn):
    """A page rotated by any right angle is put upright before OCR."""
    text = "\n".join(["The history of the ancient kingdoms of southern India"] * 12)
    img = _render(text).rotate(turn, expand=True)
    rel = "page.png"
    img.save(tmp_path / rel)
    monkeypatch.setattr(ocr.config, "ROOT", tmp_path)
    [res] = ocr.ocr_document("x", "eng", [(0, rel)])
    assert res["ocr_model"] == "eng"
    assert "kingdoms" in res["text"].lower()
    assert res["mean_conf"] > 70


@needs_tesseract
def test_wrong_catalogue_tag_loses_the_confidence_check(tmp_path, monkeypatch):
    """An English page catalogued as Hindi: OSD says Latin, and the English model also reads it
    with higher confidence than the Hindi model, so English wins."""
    text = "\n".join(["The history of the ancient kingdoms of southern India"] * 12)
    _render(text).save(tmp_path / "page.png")
    monkeypatch.setattr(ocr.config, "ROOT", tmp_path)
    [res] = ocr.ocr_document("x", "hin", [(0, "page.png")])
    assert res["ocr_model"] == "eng"
    assert "kingdoms" in res["text"].lower()
