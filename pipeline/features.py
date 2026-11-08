"""Step 4: two feature sets for the same usable books, both 100-dimensional with unit-length rows.

    python -m pipeline.features            # both sets
    python -m pipeline.features --only A   # TF-IDF + LSA only (no embedding model needed)

A. TF-IDF + LSA: word 1-2-grams and character 3-5-grams (robust to OCR errors), each L2-normalised
   and weighted equally, reduced with TruncatedSVD (latent semantic analysis), rows re-normalised.
B. Multilingual sentence embeddings (LaBSE, 109 languages incl. all 8 here): each book's clean text
   is cut into chunks, embedded, averaged; reduced with PCA to 100 dimensions, rows re-normalised.

Stopwords: per-language document frequency. A term found in more than 30% of the books *of its own
language* (the OCR model: eng, hin, san, ben, guj, tel, kan, tam) is dropped. A corpus-wide cap
would miss Hindi or Tamil function words, because each language is only an eighth of the corpus;
a per-script cap would miss Sanskrit ones, because Hindi shares the Devanagari script.
"""
import argparse
import json
import os
from collections import Counter, defaultdict

import joblib
import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from . import config, text

PROCESSED = config.DATA / "processed"
N_COMPONENTS = 100
LANG_DF_CAP = 0.3
EMBED_MODEL = "sentence-transformers/LaBSE"
CHUNK_TOKENS = 64          # words per chunk; ~128 word-pieces for Indian scripts
MAX_CHUNKS = 4             # evenly spaced across the book's 5 pages (CPU budget: ~4 chunks/s)
MAX_SEQ = 128              # word-pieces per chunk; Indian-script words split into several


def word_analyzer(tokens: list[str]) -> list[str]:
    """Unigrams + bigrams from an already-cleaned token list (module-level so it pickles)."""
    return tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])]


def language_stopwords(token_lists: list[list[str]], groups: list[str], cap: float = LANG_DF_CAP) -> set[str]:
    by_group = defaultdict(list)
    for toks, g in zip(token_lists, groups):
        by_group[g].append(set(toks))
    stop = set()
    for g, sets in by_group.items():
        if len(sets) < 20:   # too few books in this language to judge what is a function word
            continue
        df = Counter(t for st in sets for t in st)
        stop |= {t for t, c in df.items() if c / len(sets) > cap}
    return stop


def apply_stopwords(token_lists, stop):
    return [[t for t in toks if t not in stop] for toks in token_lists]


class TfidfLSA:
    """Fitted transform for feature set A; also used by the web app for a new document."""

    def __init__(self, seed: int = config.SEED):
        self.word = TfidfVectorizer(analyzer=word_analyzer, min_df=3, max_df=0.5, sublinear_tf=True,
                                    max_features=40000, dtype=np.float32)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_df=0.5,
                                    sublinear_tf=True, max_features=40000, dtype=np.float32)
        self.svd = TruncatedSVD(N_COMPONENTS, algorithm="randomized", n_iter=7, random_state=seed)
        self.stop: set[str] = set()
        self.stop_cap = LANG_DF_CAP

    def _sparse(self, token_lists, fit=False):
        joined = [" ".join(t) for t in token_lists]
        Xw = self.word.fit_transform(token_lists) if fit else self.word.transform(token_lists)
        Xc = self.char.fit_transform(joined) if fit else self.char.transform(joined)
        return sp.hstack([Xw, Xc]).tocsr() * np.float32(1 / np.sqrt(2)), Xw

    def fit_transform(self, token_lists, languages):
        self.stop = language_stopwords(token_lists, languages, self.stop_cap)
        token_lists = apply_stopwords(token_lists, self.stop)
        X, Xw = self._sparse(token_lists, fit=True)
        Z = normalize(self.svd.fit_transform(X))
        return Z.astype(np.float32), Xw

    def transform(self, token_lists):
        token_lists = apply_stopwords(token_lists, self.stop)
        X, Xw = self._sparse(token_lists)
        return normalize(self.svd.transform(X)).astype(np.float32), Xw


def chunks_of(tokens: list[str]) -> list[str]:
    pieces = [tokens[i:i + CHUNK_TOKENS] for i in range(0, len(tokens), CHUNK_TOKENS)]
    pieces = [p for p in pieces if len(p) >= 10] or ([tokens] if tokens else [])
    if len(pieces) > MAX_CHUNKS:
        idx = np.linspace(0, len(pieces) - 1, MAX_CHUNKS).round().astype(int)
        pieces = [pieces[i] for i in idx]
    return [" ".join(p) for p in pieces]


class Embedder:
    """Feature set B. The sentence-transformers model is loaded lazily (it is ~1.8 GB)."""

    def __init__(self, model_name: str = EMBED_MODEL, seed: int = config.SEED):
        self.model_name = model_name
        self.pca = PCA(N_COMPONENTS, random_state=seed)
        self._model = None

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k != "_model"} | {"_model": None}

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            # HERITAGE_EMBED_MODEL: a plain local copy of the same model (the app image uses one,
            # since the Hugging Face cache relies on symlinks that a Windows build context cannot send).
            self._model = SentenceTransformer(os.environ.get("HERITAGE_EMBED_MODEL", self.model_name), device="cpu")
            self._model.max_seq_length = MAX_SEQ
        return self._model

    def raw(self, token_lists, batch_size: int = 64, progress: bool = False) -> np.ndarray:
        doc_chunks = [chunks_of(t) for t in token_lists]
        flat = [c for cs in doc_chunks for c in cs]
        emb = self.model.encode(flat, batch_size=batch_size, normalize_embeddings=True,
                                show_progress_bar=progress, convert_to_numpy=True)
        out, i = [], 0
        for cs in doc_chunks:
            out.append(emb[i:i + len(cs)].mean(axis=0) if cs else np.zeros(emb.shape[1], np.float32))
            i += len(cs)
        return normalize(np.vstack(out))

    def fit_transform_raw(self, E: np.ndarray) -> np.ndarray:
        return normalize(self.pca.fit_transform(E)).astype(np.float32)

    def transform(self, token_lists) -> np.ndarray:
        return normalize(self.pca.transform(self.raw(token_lists))).astype(np.float32)


def load_inputs():
    docs = pd.read_csv(PROCESSED / "docs.csv")
    rows = [json.loads(l) for l in (PROCESSED / "tokens.jsonl").open(encoding="utf-8")]
    ids = [r["identifier"] for r in rows]
    toks = [r["tokens"] for r in rows]
    language = docs.set_index("identifier").loc[ids, "ocr_model"].tolist()   # eng, hin, san, ...
    return ids, toks, language


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=["A", "B"])
    args = ap.parse_args(argv)
    ids, toks, languages = load_inputs()
    out_path = PROCESSED / "features.joblib"
    bundle = joblib.load(out_path) if out_path.exists() else {}
    if bundle.get("ids") not in (None, ids):
        bundle = {}  # corpus changed: recompute everything
    bundle["ids"] = ids
    if args.only in (None, "A"):
        lsa = TfidfLSA()
        Z, Xw = lsa.fit_transform(toks, languages)
        bundle["A"] = {"Z": Z, "Xw": Xw, "transform": lsa,
                       "explained_variance": float(lsa.svd.explained_variance_ratio_.sum()),
                       "n_stopwords": len(lsa.stop),
                       "vocab_word": len(lsa.word.vocabulary_), "vocab_char": len(lsa.char.vocabulary_)}
        print(f"A: {Z.shape}, SVD explains {bundle['A']['explained_variance']:.1%} of TF-IDF variance, "
              f"{len(lsa.stop)} per-language stopwords", flush=True)
    if args.only in (None, "B"):
        emb = Embedder()
        cache = PROCESSED / "embeddings_raw.npy"
        cache_ids = PROCESSED / "embeddings_ids.json"
        if cache.exists() and cache_ids.exists() and json.loads(cache_ids.read_text()) == ids:
            E = np.load(cache)
        else:
            E = emb.raw(toks, progress=True)
            np.save(cache, E)
            cache_ids.write_text(json.dumps(ids))
        Z = emb.fit_transform_raw(E)
        bundle["B"] = {"Z": Z, "transform": emb,
                       "explained_variance": float(emb.pca.explained_variance_ratio_.sum())}
        print(f"B: {Z.shape}, PCA keeps {bundle['B']['explained_variance']:.1%} of embedding variance", flush=True)
    joblib.dump(bundle, out_path)


if __name__ == "__main__":
    # Run through the importable module so pickled classes are saved as pipeline.features.*,
    # not __main__.*, and can be loaded by the study, the export and the web app.
    from pipeline.features import main as _main
    _main()
