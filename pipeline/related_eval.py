"""How often a book's 10 nearest neighbours are in another script, with and without per-language centring.

Train books only; same reduction as scripts/centring_effect.py (subtract each language's mean, normalise,
PCA to 100 dims, normalise). Writes reports/features/related.json.

    python -m pipeline.related_eval
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

from . import config

K = 10
OUT = config.REPORTS / "features" / "related.json"


def _share(X: np.ndarray, script: np.ndarray) -> float:
    X = normalize(PCA(min(100, *X.shape), random_state=config.SEED).fit_transform(X))
    nn = NearestNeighbors(n_neighbors=K + 1).fit(X).kneighbors(X, return_distance=False)[:, 1:]
    return float((script[nn] != script[:, None]).mean())


def run(features_path, docs_path, out: Path = OUT) -> dict:
    """features_path: embeddings_raw_<FS>.npy (ids in the sibling embeddings_ids_<FS>.json); docs_path: docs.csv."""
    features_path = Path(features_path)
    E = np.load(features_path)
    key = json.loads(features_path.with_name(features_path.name.replace("raw", "ids").replace(".npy", ".json")).read_text())
    ids = key["ids"] if isinstance(key, dict) else key
    d = pd.read_csv(docs_path, low_memory=False).set_index("identifier").loc[ids]
    train = (d["split"] == "train").to_numpy()
    E, lang, script = E[train], d["lang_tag"].to_numpy()[train], d["script"].to_numpy()[train]
    means = {l: E[lang == l].mean(axis=0) for l in np.unique(lang)}
    centred = normalize(E - np.vstack([means[l] for l in lang]))
    res = {"knn_other_script_share": {"centred": _share(centred, script), "uncentred": _share(E, script)},
           "k": K, "books": int(train.sum()), "split": "train"}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2))
    return res


def main() -> None:
    fs = json.loads((config.STUDY / "selection_train.json").read_text())["chosen"]
    print(json.dumps(run(config.PROCESSED / f"embeddings_raw_{fs}.npy", config.PROCESSED / "docs.csv"), indent=2))


if __name__ == "__main__":
    main()
