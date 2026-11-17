"""Golden output of study.run_feature_set on a fixed synthetic corpus.

Guards refactors of the study (distance reuse, linkage caching): the chosen distance, the chosen
hierarchical and DBSCAN settings, their scores and the bootstrap ARIs must not change. To refresh the
snapshot after an intended change of results:  GRANTHA_UPDATE_GOLDEN=1 pytest tests/test_study_golden.py
"""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from pipeline import features, study
from tests.test_study import corpus

GOLDEN = Path(__file__).parent / "golden" / "study_run_feature_set.json"


def snapshot() -> dict:
    toks, docs = corpus()
    lsa = features.TfidfLSA()
    lsa.svd.n_components = 20
    lsa.stop_cap = 0.5
    Z, Xw = lsa.fit_transform(toks, docs["script"].tolist())
    bundle = {"A": {"Z": Z, "Xw": Xw, "transform": lsa, "explained_variance": 0.5}, "ids": docs["identifier"].tolist()}
    res = study.run_feature_set("A", bundle, docs, np.random.default_rng(7))
    h, d = res["hierarchical"], res["dbscan"]
    return {"distance": {k: res["distance"][k] for k in ("chosen", "wins")},
            "cophenetic": {m: {k: v for k, v in r.items() if k.startswith("cophenetic")}
                           for m, r in res["distance"]["metrics"].items()},
            "hier_final": h["final"], "hier_rule_met": h["rule_met"], "hier_labels": list(map(int, h["labels"])),
            "hier_boot": h["bootstrap_ari"], "dbscan_final": d["final"],
            "dbscan_labels": list(map(int, d["labels"])),
            "grid_silhouettes": [[r["linkage"], r["metric"], r["k"], r["silhouette"]] for r in h["grid"]]}


def test_study_output_matches_golden():
    got = json.loads(json.dumps(study.clean_json(snapshot())))
    if os.environ.get("GRANTHA_UPDATE_GOLDEN") or not GOLDEN.exists():
        GOLDEN.write_text(json.dumps(got, indent=1, sort_keys=True), encoding="utf-8")
        pytest.skip("golden snapshot written")
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert _close(got, want)


def _close(a, b, path="") -> bool:
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        return all(_close(a[k], b[k], f"{path}.{k}") for k in a)
    if isinstance(a, list):
        assert len(a) == len(b), path
        return all(_close(x, y, f"{path}[{i}]") for i, (x, y) in enumerate(zip(a, b)))
    if isinstance(a, float) and isinstance(b, float):
        # Choices and labels must match exactly (below); scores only to 1e-5. BLAS builds and thread counts
        # change float summation order, which moved scores by up to 2.5e-6 between machines (CI vs the snapshot).
        assert a == pytest.approx(b, rel=1e-5, abs=1e-9), path
        return True
    assert a == b, path
    return True
