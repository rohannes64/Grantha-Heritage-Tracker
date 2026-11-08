"""OCR for uploaded scans: page images or a PDF (first pages only). Same Tesseract settings,
orientation fix and script routing as the archive pipeline."""
import io

from PIL import Image, ImageOps

from pipeline import config
from pipeline.ocr import _lines_from_data, _osd

MAX_PAGES = 5
PDF_DPI = 200


class OCRInputError(ValueError):
    pass


def images_from_upload(data: bytes, filename: str) -> list[Image.Image]:
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        import fitz  # PyMuPDF
        try:
            pdf = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            raise OCRInputError(f"could not open the PDF: {e}") from e
        out = []
        for page in list(pdf)[:MAX_PAGES]:
            pix = page.get_pixmap(dpi=PDF_DPI, colorspace=fitz.csGRAY)
            out.append(Image.frombytes("L", (pix.width, pix.height), pix.samples))
        if not out:
            raise OCRInputError("the PDF has no pages")
        return out
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise OCRInputError("the file is not an image or PDF we can read") from e
    frames = []
    for i in range(min(getattr(img, "n_frames", 1), MAX_PAGES)):  # multi-page TIFF
        img.seek(i)
        frames.append(img.copy())
    return frames


def ocr_images(images: list[Image.Image], lang: str | None) -> dict:
    """lang: an IA language code from config.LANGUAGES, or None to detect the script per page."""
    import pytesseract
    pages, scripts = [], []
    prepared = []
    for img in images:
        g = ImageOps.grayscale(ImageOps.exif_transpose(img))
        script, rotate, sconf = _osd(g)
        if rotate and sconf >= 2:
            g = g.rotate(-rotate, expand=True)
        prepared.append(g)
        if script and sconf >= 1:
            scripts.append(script)
    if lang:
        model, script = config.LANGUAGES[lang]["tess"], config.LANGUAGES[lang]["script"]
    elif scripts:
        script = max(set(scripts), key=scripts.count)
        model = config.SCRIPT_MODEL.get(script, "eng")
    else:
        model, script = "eng", "Latin"
    texts, conf_sum, words = [], 0.0, 0
    for g in prepared:
        d = pytesseract.image_to_data(g, lang=model, config="--oem 1 --psm 3", output_type=pytesseract.Output.DICT)
        t, mean, n = _lines_from_data(d)
        texts.append(t)
        if mean is not None:
            conf_sum += mean * n
            words += n
    return {"text": "\n\n".join(texts), "ocr_conf": (conf_sum / words) if words else 0.0, "model": model,
            "script": script, "pages": len(prepared), "script_detected": not lang}
