"""SQLite corpus store. Only the main process writes; worker processes return results."""
import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    identifier      TEXT PRIMARY KEY,
    lang_tag        TEXT NOT NULL,      -- language code from the catalogue
    era             TEXT NOT NULL,      -- sampling stratum
    sample_rank     INTEGER NOT NULL,   -- order within the language's draw (pilot = lowest ranks)
    title           TEXT,
    creator         TEXT,
    date_raw        TEXT,
    year            INTEGER,
    publisher       TEXT,
    source_library  TEXT,
    scanning_centre TEXT,
    subject_field   TEXT,               -- IA 'subject': usually the scanning centre, NOT a topic
    classification  TEXT,               -- dc.subject.classification values joined by ' | '
    total_pages     INTEGER,
    ia_ocr_files    TEXT,               -- JSON: names of IA per-page OCR files, if any
    status          TEXT NOT NULL DEFAULT 'drawn',  -- drawn | harvested | skipped | failed
    note            TEXT
);
CREATE TABLE IF NOT EXISTS pages (
    identifier   TEXT NOT NULL REFERENCES documents(identifier),
    leaf         INTEGER NOT NULL,
    position     REAL NOT NULL,
    image_path   TEXT,
    ocr_model    TEXT,
    osd_script   TEXT,
    text         TEXT,
    mean_conf    REAL,
    n_words      INTEGER,
    script_ratio REAL,
    ia_text      TEXT,
    ia_similarity REAL,
    PRIMARY KEY (identifier, leaf)
);
CREATE INDEX IF NOT EXISTS idx_docs_lang ON documents(lang_tag, sample_rank);
"""


def connect(path: Path = config.DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=60)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con
