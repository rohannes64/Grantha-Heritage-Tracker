"""Check a new document against the existing groups, without rerunning the analysis.

- Text is cleaned exactly as the archive books were (pipeline.text) and turned into the same
  features with the saved transform.
- Hierarchical group: nearest group centre; the distance is compared with how far that group's
  own books sit from its centre, which gives a plain confidence level.
- DBSCAN group: joins a group only if it lies within eps of one of that group's core books;
  otherwise it is "noise" - not close enough to any dense group.
- The app abstains (says it cannot judge) when the OCR is too weak or there is too little text.
"""
from collections import Counter

import joblib
import numpy as np
from sklearn.metrics import pairwise_distances

from pipeline import config, text
from pipeline.features import apply_stopwords

MIN_TOKENS_TO_ASSIGN = 20      # below this, no assignment at all
MIN_TOKENS_CONFIDENT = 100     # same bar the archive books had to clear


def detect_script(raw: str) -> str:
    counts = Counter(s for s in (text.script_of_char(c) for c in raw if c.isalpha()) if s)
    if not counts:
        return "Latin"
    indic = {s: n for s, n in counts.items() if s != "Latin"}
    # A book in an Indian script often quotes English; prefer the Indian script if it is substantial.
    if indic and max(indic.values()) >= 0.3 * sum(counts.values()):
        return max(indic, key=indic.get)
    return counts.most_common(1)[0][0]


class Checker:
    def __init__(self, bundle: dict):
        self.b = bundle
        self.Z = bundle["Z"].astype(np.float64)
        self.docs = bundle["docs"]
        self.index = {d["identifier"]: i for i, d in enumerate(self.docs)}
        h, d = bundle["hier"], bundle["dbscan"]
        self.core_Z = self.Z[d["core_idx"]]
        self.core_labels = np.asarray(d["labels"])[d["core_idx"]]
        lsa = bundle["lsa"]
        self.word_terms = np.empty(len(lsa.word.vocabulary_), dtype=object)
        for t, j in lsa.word.vocabulary_.items():
            self.word_terms[j] = t

    @classmethod
    def load(cls, path=config.DATA / "model" / "bundle.joblib") -> "Checker":
        return cls(joblib.load(path))

    def features(self, tokens: list[str], lang: str | None = None, script: str | None = None) -> np.ndarray:
        t = self.b["transform"]
        if self.b["feature_set"] == "A":
            return t.transform([tokens])[0]
        return t.transform([tokens], langs=[lang], scripts=[script])

    def shared_terms(self, tokens: list[str], idx: int, top: int = 8) -> list[str]:
        lsa = self.b["lsa"]
        v = lsa.word.transform(apply_stopwords([tokens], lsa.stop))
        w = self.b["Xw"][idx]
        prod = v.multiply(w).tocoo()
        order = np.argsort(prod.data)[::-1][:top]
        return [self.word_terms[prod.col[i]] for i in order]

    def check_text(self, raw: str, script: str | None = None, ocr_conf: float | None = None,
                   lang: str | None = None) -> dict:
        script = script or detect_script(raw)
        tokens = text.remove_stopwords(text.clean_tokens(raw, script))
        th = self.b["thresholds"]
        cautions = []
        if ocr_conf is not None and ocr_conf < th["min_conf"]:
            cautions.append(f"OCR confidence is {ocr_conf:.0f}, below the {th['min_conf']:.0f} the archive books had to reach.")
        if len(tokens) < MIN_TOKENS_CONFIDENT:
            cautions.append(f"Only {len(tokens)} readable words; archive books had at least {MIN_TOKENS_CONFIDENT}.")
        base = {"script": script, "tokens": len(tokens), "ocr_conf": ocr_conf, "cautions": cautions,
                "feature_set": self.b["feature_set"], "feature_name": self.b["feature_name"]}
        if len(tokens) < MIN_TOKENS_TO_ASSIGN:
            return base | {"status": "abstain",
                           "message": "Too little readable text to compare this document with the archive."}

        z = self.features(tokens, lang, script).reshape(1, -1).astype(np.float64)
        h, d = self.b["hier"], self.b["dbscan"]

        dc = pairwise_distances(z, h["centroids"], metric=h["metric"])[0]
        c = int(np.argmin(dc))
        sp = h["spread"][c]
        if dc[c] <= sp["p50"]:
            level = "strong"
        elif dc[c] <= sp["p90"]:
            level = "good"
        elif dc[c] <= sp["max"]:
            level = "weak"
        else:
            level = "outside"
        runner_up = int(np.argsort(dc)[1]) if len(dc) > 1 else None

        dcore = pairwise_distances(z, self.core_Z, metric=d["metric"])[0]
        j = int(np.argmin(dcore))
        in_dense = bool(dcore[j] <= d["eps"])
        dlab = int(self.core_labels[j]) if in_dense else -1

        dall = pairwise_distances(z, self.Z, metric=h["metric"])[0]
        nearest = np.argsort(dall)[:5]
        matches = [self.docs[i] | {"distance": float(dall[i]), "hier": int(h["labels"][i]),
                                   "dbscan": int(d["labels"][i]), "shared_terms": self.shared_terms(tokens, i)}
                   for i in nearest]
        xy = self.b["pca"].transform(z)[0]
        status = "caution" if cautions else "ok"
        return base | {
            "status": status,
            "hierarchical": {"cluster": c, "name": h["names"][str(c)], "distance": float(dc[c]), "level": level,
                             "spread": sp, "runner_up": runner_up,
                             "runner_up_name": None if runner_up is None else h["names"][str(runner_up)],
                             "runner_up_distance": None if runner_up is None else float(dc[runner_up])},
            "dbscan": {"cluster": dlab, "name": d["names"].get(str(dlab)) if dlab != -1 else None,
                       "nearest_core_distance": float(dcore[j]), "eps": d["eps"], "in_dense_group": in_dense},
            "matches": matches,
            "pca": {"x": float(xy[0]), "y": float(xy[1])},
        }
