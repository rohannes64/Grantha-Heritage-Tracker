"""Project-wide settings. Every number that shapes the sample lives here."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = Path(os.environ.get("HERITAGE_DB", DATA / "corpus.sqlite"))  # override for dry runs on a snapshot
FRAME_DIR = DATA / "frame"      # full sampling frame per language (identifiers + dates)
PAGES_DIR = DATA / "pages"      # downloaded page images (deleted after OCR in the full run)
CACHE_DIR = DATA / "cache"      # cached Internet Archive metadata
REPORTS = ROOT / "reports"

# Source: Internet Archive mirror of the Digital Library of India.
COLLECTION = "digitallibraryindia"
IA_SEARCH = "https://archive.org/services/search/v1/scrape"
IA_METADATA = "https://archive.org/metadata/{id}"
IA_DOWNLOAD = "https://archive.org/download/{id}/{name}"
IA_PAGE = "https://archive.org/download/{id}/page/n{leaf}_w{width}.jpg"
USER_AGENT = "heritage-topics/0.1 (SIH26096 student research project; polite crawler)"
REQUEST_INTERVAL = 1.0   # seconds between requests to archive.org
PAGE_WIDTH = 1200        # requested width; for DLI items the archive serves full size (~2200 px, 0.7-1 MB) anyway

# Languages: IA language code -> display name, Tesseract model, expected script.
LANGUAGES = {
    "eng": {"name": "English",   "tess": "eng", "script": "Latin"},
    "hin": {"name": "Hindi",     "tess": "hin", "script": "Devanagari"},
    "san": {"name": "Sanskrit",  "tess": "san", "script": "Devanagari"},
    "ben": {"name": "Bengali",   "tess": "ben", "script": "Bengali"},
    "guj": {"name": "Gujarati",  "tess": "guj", "script": "Gujarati"},
    "tel": {"name": "Telugu",    "tess": "tel", "script": "Telugu"},
    "kan": {"name": "Kannada",   "tess": "kan", "script": "Kannada"},
    "tam": {"name": "Tamil",     "tess": "tam", "script": "Tamil"},
}

# Unicode blocks used to measure how much OCR output is in the expected script.
SCRIPT_RANGES = {
    "Latin":      [(0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)],
    "Devanagari": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],
    "Bengali":    [(0x0980, 0x09FF)],
    "Gujarati":   [(0x0A80, 0x0AFF)],
    "Tamil":      [(0x0B80, 0x0BFF)],
    "Telugu":     [(0x0C00, 0x0C7F)],
    "Kannada":    [(0x0C80, 0x0CFF)],
}

# Tesseract OSD script names -> our script names (OSD uses "Han", "Latin", "Devanagari", ...).
OSD_SCRIPT = {
    "Latin": "Latin", "Devanagari": "Devanagari", "Bengali": "Bengali",
    "Gujarati": "Gujarati", "Tamil": "Tamil", "Telugu": "Telugu", "Kannada": "Kannada",
}
# Script -> Tesseract model when the detected script disagrees with the catalogue tag.
SCRIPT_MODEL = {
    "Latin": "eng", "Devanagari": "hin", "Bengali": "ben", "Gujarati": "guj",
    "Tamil": "tam", "Telugu": "tel", "Kannada": "kan",
}

# Heritage scope: published up to 1960, or undated.
MAX_YEAR = 1960
ERA_BANDS = [
    ("pre-1900", None, 1899),
    ("1900-1919", 1900, 1919),
    ("1920-1939", 1920, 1939),
    ("1940-1960", 1940, 1960),
    ("undated", None, None),
]

SEED = 2026
PILOT_PER_LANG = 50
FULL_PER_LANG = 375
PAGE_POSITIONS = (0.15, 0.30, 0.50, 0.70, 0.85)  # fractions through the book
MIN_PAGES = 20           # shorter items are pamphlets or broken scans; skipped
