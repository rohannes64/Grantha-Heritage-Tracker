"""How much per-language centring reduces script dependence, on the train books only.

Same reduction and clustering as the study (PCA to 100 dims, average linkage, Euclidean, k groups),
once on the raw embeddings and once after subtracting each language's mean vector.
Writes reports/study/centring_effect_<FS>.json.

    python scripts/centring_effect.py            # the feature set, linkage and k chosen on the train books
    python scripts/centring_effect.py G 6        # or a given feature set and k (average linkage)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.decomposition import PCA
from sklearn.metrics import normalized_mutual_info_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

BASE = Path(__file__).resolve().parents[1]
chosen = json.loads((BASE / "reports" / "study" / "selection_train.json").read_text())
fs = sys.argv[1] if len(sys.argv) > 1 else chosen["chosen"]
k = int(sys.argv[2]) if len(sys.argv) > 2 else chosen["setting"]["k"]
method = chosen["setting"]["linkage"] if len(sys.argv) <= 1 else "average"
P = BASE / "data" / "processed"
E = np.load(P / f"embeddings_raw_{fs}.npy")
key = json.loads((P / f"embeddings_ids_{fs}.json").read_text())
ids = key["ids"] if isinstance(key, dict) else key
d = pd.read_csv(P / "docs.csv", low_memory=False).set_index("identifier").loc[ids]
train = (d["split"] == "train").to_numpy()
E, lang, script = E[train], d["lang_tag"].to_numpy()[train], d["script"].to_numpy()[train]
means = {l: E[lang == l].mean(axis=0) for l in np.unique(lang)}
centred = normalize(E - np.vstack([means[l] for l in lang]))

out = {"feature_set": fs, "k": k, "train_books": int(train.sum()), "linkage": method, "metric": "euclidean"}
for name, X in (("uncentred", E), ("centred", centred)):
    X = normalize(PCA(100, random_state=2026).fit_transform(X))
    groups = fcluster(linkage(pdist(X), method), k, "maxclust")
    nn = NearestNeighbors(n_neighbors=11).fit(X).kneighbors(X, return_distance=False)[:, 1:]
    out[name] = {"nmi_script": float(normalized_mutual_info_score(script, groups)),
                 "knn10_same_script": float((script[nn] == script[:, None]).mean()),
                 "largest_group_share": float(np.bincount(groups).max() / len(groups))}
(BASE / "reports" / "study" / f"centring_effect_{fs}.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
