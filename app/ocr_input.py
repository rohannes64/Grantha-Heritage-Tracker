"""OCR for uploaded scans: page images or a PDF (first pages only). Same Tesseract settings,
orientation fix and script routing as the archive pipeline."""
import io
import math
import warnings

from PIL import Image, ImageOps

from pipeline import config
from pipeline.ocr import _lines_from_data, _osd

MAX_PAGES = 5
PDF_DPI = 200
MAX_PIXELS = 40_000_000   # per page: an A3 sheet at 300 dpi is ~17 MP; anything far beyond is not a book page


class OCRInputError(ValueError):
    pass


def images_from_upload(data: bytes, filename: str) -> list[Image.Image]:
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        import pymupdf as fitz  # the `fitz` module name is deprecated since PyMuPDF 1.24.3
        try:
            pdf = fitz.open(stream=data, filetype="pdf")
        except Exception as e:
            raise OCRInputError(f"could not open the PDF: {e}") from e
        out = []
        for i in range(min(pdf.page_count, MAX_PAGES)):
            page = pdf.load_page(i)
            w_in, h_in = page.rect.width / 72, page.rect.height / 72
            # render at PDF_DPI, or lower if the page declares a size that would exceed MAX_PIXELS
            dpi = min(PDF_DPI, int(math.sqrt(MAX_PIXELS / max(w_in * h_in, 1e-6))))
            pix = page.get_pixmap(dpi=max(dpi, 1), colorspace=fitz.csGRAY)
            out.append(Image.frombytes("L", (pix.width, pix.height), pix.samples))
        if not out:
            raise OCRInputError("the PDF has no pages")
        return out
    try:
        img = Image.open(io.BytesIO(data))           # reads the header only
    except Exception as e:
        raise OCRInputError("the file is not an image or PDF we can read") from e
    if img.width * img.height > MAX_PIXELS:
        raise OCRInputError(f"the image is too large ({img.width} x {img.height} pixels); scan the page at 300 dpi or less")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img.load()
    except Exception as e:
        raise OCRInputError("the file is not an image or PDF we can read") from e
    frames = []
    for i in range(min(getattr(img, "n_frames", 1), MAX_PAGES)):  # multi-page TIFF
        img.seek(i)
        frames.append(img.copy())
    return frames


# Models tried in auto mode when script detection is unsure. Sanskrit shares Devanagari with Hindi
# and gets its own reading, since the Sanskrit model handles conjuncts the Hindi one misses.
AUTO_MODELS = ["eng", "hin", "san", "ben", "guj", "tel", "kan", "tam"]
CONFIDENT = 70.0     # a first-page mean confidence this high settles the model without trying others
MODEL_TO_LANG = {v["tess"]: k for k, v in config.LANGUAGES.items()}


def _read(g, model):
    import pytesseract
    d = pytesseract.image_to_data(g, lang=model, config="--oem 1 --psm 3", output_type=pytesseract.Output.DICT)
    return _lines_from_data(d)


def _auto_model(first, detected: str | None) -> tuple[str, dict]:
    """Pick the Tesseract model for an untagged page. Tesseract's script detector misreads several
    Indic scripts (it called a Tamil page Latin and most Gujarati pages Bengali in the pilot), so its
    guess is only kept when it reads the first page confidently; otherwise every model reads the first
    page and the most confident one wins. Returns the model and the first-page readings."""
    from concurrent.futures import ThreadPoolExecutor
    readings = {}
    guess = config.SCRIPT_MODEL.get(detected or "", "eng")
    readings[guess] = _read(first, guess)
    if (readings[guess][1] or 0.0) >= CONFIDENT:
        return guess, readings
    rest = [m for m in AUTO_MODELS if m not in readings]
    with ThreadPoolExecutor(max_workers=4) as pool:      # each call is its own tesseract process
        for m, r in zip(rest, pool.map(lambda m: _read(first, m), rest)):
            readings[m] = r
    best = max(readings, key=lambda m: (readings[m][1] or 0.0))
    return best, readings


def ocr_images(images: list[Image.Image], lang: str | None) -> dict:
    """lang: an IA language code from config.LANGUAGES, or None to detect the language."""
    scripts = []
    prepared = []
    for img in images:
        g = ImageOps.grayscale(ImageOps.exif_transpose(img))
        script, rotate, sconf = _osd(g)
        if rotate and sconf >= 2:
            g = g.rotate(-rotate, expand=True)
        prepared.append(g)
        if script and sconf >= 1:
            scripts.append(script)
    first_reading = {}
    if lang:
        model = config.LANGUAGES[lang]["tess"]
    else:
        detected = max(set(scripts), key=scripts.count) if scripts else None
        model, first_reading = _auto_model(prepared[0], detected)
    script = config.LANGUAGES[MODEL_TO_LANG[model]]["script"]
    texts, conf_sum, words = [], 0.0, 0
    for i, g in enumerate(prepared):
        t, mean, n = first_reading[model] if i == 0 and model in first_reading else _read(g, model)
        texts.append(t)
        if mean is not None:
            conf_sum += mean * n
            words += n
    return {"text": "\n\n".join(texts), "ocr_conf": (conf_sum / words) if words else 0.0, "model": model,
            "script": script, "pages": len(prepared), "script_detected": not lang}
