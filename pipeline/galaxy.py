"""Galaxy data: a 3-D PCA of every book's vector, with and without per-language centring.

    python -m pipeline.galaxy

Reads data/processed/embeddings_raw_<FS>.npy + embeddings_ids_<FS>.json (FS = the bundle's feature set),
the bundle (book order, hierarchical groups and language), and writes web/data/galaxy.json.
Centring is the same as scripts/centring_effect.py: subtract each language's mean vector, then normalise.
"""
import json

import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize

from . import config

PROCESSED = config.PROCESSED
WEB_DATA = config.ROOT / "web" / "data"


def _pca3(X: np.ndarray):
    p = PCA(3, random_state=2026)
    coords = p.fit_transform(X)
    return ([[round(float(v), 4) for v in row] for row in coords],
            [float(v) for v in p.explained_variance_ratio_])


def build(E: np.ndarray, ids: list[str], lang: list[str], groups: list[int]) -> dict:
    """E: raw embeddings, one row per id. Both views list the books in the order of `ids`."""
    E = np.asarray(E, dtype=float)
    lang_a = np.asarray(lang)
    means = {l: E[lang_a == l].mean(axis=0) for l in np.unique(lang_a)}
    centred = normalize(E - np.vstack([means[l] for l in lang]))
    unc_xyz, unc_ev = _pca3(normalize(E))
    cen_xyz, cen_ev = _pca3(centred)
    return {"n": len(ids),
            "views": {"centred": cen_xyz, "uncentred": unc_xyz},
            "explained": {"centred": cen_ev, "uncentred": unc_ev},
            "books": [{"identifier": i, "lang_tag": str(l), "group": int(g)}
                      for i, l, g in zip(ids, lang, groups)]}


def main() -> None:
    bundle = joblib.load(config.DATA / "model" / "bundle.joblib")
    fs, order = bundle["feature_set"], list(bundle["ids"])
    groups = [int(g) for g in bundle["hier"]["labels"]]
    E = np.load(PROCESSED / f"embeddings_raw_{fs}.npy")
    key = json.loads((PROCESSED / f"embeddings_ids_{fs}.json").read_text(encoding="utf-8"))
    emb_ids = key["ids"] if isinstance(key, dict) else key
    row = {i: n for n, i in enumerate(emb_ids)}
    missing = [i for i in order if i not in row]
    if missing:
        raise SystemExit(f"{len(missing)} of the bundle's {len(order)} books have no raw embedding "
                         f"(embeddings_raw_{fs}.npy): rebuild the embeddings first")
    lang = [str(d["lang_tag"]) for d in bundle["docs"]]      # bundle docs are in `ids` order
    g = build(E[[row[i] for i in order]], order, lang, groups)
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "galaxy.json").write_text(json.dumps(g, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote galaxy.json for {g['n']} books")


if __name__ == "__main__":
    main()
