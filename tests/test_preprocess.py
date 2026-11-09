"""Whole-book text windows and the train/val/test split."""
import numpy as np
import pandas as pd

from pipeline import preprocess


def test_windows_cover_the_whole_book_evenly():
    toks = [f"w{i}" for i in range(100_000)]
    w = preprocess.windows(toks)
    assert len(w) == preprocess.WINDOWS * preprocess.WINDOW_TOKENS
    assert w[0] == "w0" and w[-1] == "w99999"          # first and last windows reach both ends
    short = toks[:500]
    assert preprocess.windows(short) == short           # short texts are kept whole


def test_splits_are_stratified_reproducible_and_skip_unusable_books():
    df = pd.DataFrame({"lang_tag": ["hin"] * 100 + ["tam"] * 50, "usable": [1] * 140 + [0] * 10})
    a, b = preprocess.assign_splits(df), preprocess.assign_splits(df)
    assert a.equals(b)
    assert a[df["usable"] == 0].isna().all()
    hin = a[df["lang_tag"] == "hin"].value_counts()
    assert (hin["train"], hin["val"], hin["test"]) == (60, 20, 20)
    tam = a[(df["lang_tag"] == "tam") & (df["usable"] == 1)].value_counts()
    assert tam.sum() == 40 and tam["train"] == 24
