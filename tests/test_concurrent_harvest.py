import sqlite3
import pytest
from pipeline import db, harvest

def test_db_wal_mode_and_concurrency(tmp_path):
    test_db = tmp_path / "test_corpus.sqlite"
    con = db.connect(test_db)
    mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    sync = con.execute("PRAGMA synchronous").fetchone()[0]
    assert sync in (1, "NORMAL", "1")  # NORMAL mode
    con.close()
