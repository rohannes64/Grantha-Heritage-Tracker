"""Evaluation integrity: stable splits, the sensitivity refit's metric, and the page check's book set."""
import numpy as np
import pandas as pd

from pipeline import preprocess


def _books(n, start=0):
    langs = ["eng", "hin", "tam", "san"]
    return pd.DataFrame({"usable": 1, "lang_tag": [langs[i % 4] for i in range(start, start + n)]},
                        index=[f"in.ernet.dli.2015.{i}" for i in range(start, start + n)])


def test_existing_books_keep_their_split_when_the_corpus_grows():
    small = _books(3000)
    grown = pd.concat([small, _books(10000, start=3000)])
    before = preprocess.assign_splits(small)
    after = preprocess.assign_splits(grown)
    assert (after.loc[small.index] == before).all()


def test_splits_are_close_to_60_20_20_in_every_language():
    df = _books(12000)
    split = preprocess.assign_splits(df)
    for _, g in split.groupby(df["lang_tag"]):
        shares = g.value_counts(normalize=True)
        assert abs(shares["train"] - 0.6) < 0.03 and abs(shares["val"] - 0.2) < 0.03 and abs(shares["test"] - 0.2) < 0.03


def test_unusable_books_get_no_split():
    df = _books(100)
    df.iloc[:10, df.columns.get_loc("usable")] = 0
    split = preprocess.assign_splits(df)
    assert split.iloc[:10].isna().all() and split.iloc[10:].notna().all()


def test_sensitivity_refits_with_the_chosen_metric(monkeypatch):
    from pipeline import sensitivity
    seen = []
    real = sensitivity.linkage
    monkeypatch.setattr(sensitivity, "linkage", lambda X, method, metric: seen.append(metric) or real(X, method, metric=metric))
    X = np.random.default_rng(0).normal(size=(40, 5))
    sensitivity.cluster(X, {"linkage": "average", "metric": "cityblock", "k": 3})
    assert seen == ["cityblock"]


def test_page_check_leaves_out_books_built_from_their_own_pages():
    from pipeline import evaluate
    docs = pd.DataFrame({"text_source": ["hocr", "tesseract_pages", "djvu"]}, index=["a", "b", "c"])
    groups = {"a": 0, "b": 1, "c": 2}
    kept, left_out = evaluate.page_check_books(groups, docs)
    assert kept == {"a": 0, "c": 2} and left_out == 1


def test_embedding_cache_is_invalidated_when_the_text_changes(tmp_path, monkeypatch):
    from pipeline import features
    calls = []

    class Fake:
        def raw(self, toks, progress=False):
            calls.append(len(toks))
            return np.ones((len(toks), 4), np.float32) * len(calls)

    monkeypatch.setattr(features, "PROCESSED", tmp_path)
    monkeypatch.setattr(features, "make_embedder", lambda fs: Fake())
    ids = ["a", "b"]
    features.raw_embeddings("V", ids, [["five", "pages"], ["only"]])
    features.raw_embeddings("V", ids, [["five", "pages"], ["only"]])          # same text: cached
    assert len(calls) == 1
    E = features.raw_embeddings("V", ids, [["whole", "book", "text"], ["only"]])   # same ids, new text
    assert len(calls) == 2 and E[0, 0] == 2


def test_fulltext_shards_partition_a_language():
    from pipeline.fulltext import shard_rows
    rows = list(range(103))
    parts = [shard_rows(rows, i, 3) for i in range(3)]
    assert sorted(x for part in parts for x in part) == rows and all(len(p) >= 34 for p in parts)


def test_subject_scores_report_bootstrap_intervals_around_the_estimate():
    from pipeline import evaluate
    rng = np.random.default_rng(0)
    ids = [f"b{i}" for i in range(200)]
    subj = ["law" if i % 2 else "poetry" for i in range(200)]
    noisy = [s if rng.random() > 0.3 else ("poetry" if s == "law" else "law") for s in subj]   # ~70% right
    groups = {i: (1 if s == "law" else 0) for i, s in zip(ids, subj)}
    docs = pd.DataFrame({"script": ["Latin"] * 200}, index=ids)
    labels = pd.DataFrame({"identifier": ids, "subject": noisy})
    out = evaluate.subject_scores({i: groups[i] for i in ids[:100]}, {i: groups[i] for i in ids[100:]}, docs,
                                  labels, np.random.default_rng(1))
    lo, hi = out["accuracy_groups_ci95"]
    assert lo <= out["accuracy_groups"] <= hi and 0.5 < lo and hi < 0.9
    plo, phi = out["points_above_best_baseline_ci95"]
    assert plo <= out["points_above_best_baseline"] <= phi
