"""Step 4: three feature sets for the same usable books, all 100-dimensional with unit-length rows.

    python -m pipeline.features --fit train   # evaluation run: fit on train books, transform the rest
    python -m pipeline.features --fit all     # final run: fit on every usable book (the app's model)
    python -m pipeline.features --only A      # one set only

The bundle's "ids" are the books the transforms were fitted on (and that the study clusters);
"holdout" holds the other usable books, transformed with the same fitted transforms, for evaluation.

A. TF-IDF + LSA: word 1-2-grams and character 3-5-grams (robust to OCR errors), each L2-normalised
   and weighted equally, reduced with TruncatedSVD (latent semantic analysis), rows re-normalised.
B. Multilingual sentence embeddings (LaBSE, 109 languages incl. all 8 here): each book's clean text
   is cut into chunks, embedded, averaged; reduced with PCA to 100 dimensions, rows re-normalised.
D. BGE-M3 (BAAI/bge-m3, trained for multilingual search, 100+ languages): the same recipe. Chosen in
   validation round 1 because, after language centring, it carries the most topic information
   (docs/accuracy_plan.md: 68.2% vs LaBSE 64.9% and IndicSBERT 64.5%, 7-NN on labelled train+val books).
C. IndicSBERT (l3cube-pune/indic-sentence-similarity-sbert): the same recipe with a sentence model
   trained on Indian languages (Hindi, Marathi, Kannada, Tamil, Telugu, Malayalam, Gujarati, Odia,
   Punjabi, Bengali and English). Sanskrit is read through its Devanagari script.

Stopwords: per-language document frequency. A term found in more than 30% of the books *of its own
language* (the OCR model: eng, hin, san, ben, guj, tel, kan, tam) is dropped. A corpus-wide cap
would miss Hindi or Tamil function words, because each language is only an eighth of the corpus;
a per-script cap would miss Sanskrit ones, because Hindi shares the Devanagari script.
"""
import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

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
INDIC_MODEL = "l3cube-pune/indic-sentence-similarity-sbert"
BGE_MODEL = "BAAI/bge-m3"
MODELS = {"B": EMBED_MODEL, "C": INDIC_MODEL, "D": BGE_MODEL}
SET_NAMES = {"A": "TF-IDF + LSA", "B": "LaBSE embeddings", "C": "IndicSBERT embeddings", "D": "BGE-M3 embeddings"}
CHUNK_TOKENS = 64          # words per chunk; ~128 word-pieces for Indian scripts
MAX_CHUNKS = 10            # evenly spaced across the book's training text (CPU budget: ~4 chunks/s)
MAX_SEQ = 128              # word-pieces per chunk; Indian-script words split into several
# Multilingual embeddings place each language in its own region, so groups follow language before topic.
# Subtracting each language's mean (fitted on the fit books only) removes that offset; a new document is
# centred by its OCR language. Validation round 1 (docs/evaluation_log.md): script NMI 0.38 -> 0.04.
CENTRE_BY_LANGUAGE = True


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


def model_slug(name: str) -> str:
    return name.replace("/", "__")


def local_model_path(name: str) -> str:
    """HERITAGE_MODEL_DIR/<slug>: a plain saved copy of the model (the app image uses one, since the
    Hugging Face cache relies on symlinks that a Windows build context cannot send). Else the hub name."""
    base = os.environ.get("HERITAGE_MODEL_DIR")
    if base and (Path(base) / model_slug(name) / "config.json").exists():
        return str(Path(base) / model_slug(name))
    return name


def embed_device() -> str:
    """cuda when a GPU is visible (the batch embedding run), else cpu (the app image). HERITAGE_DEVICE overrides."""
    if os.environ.get("HERITAGE_DEVICE"):
        return os.environ["HERITAGE_DEVICE"]
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


class Embedder:
    """Feature set B. The sentence-transformers model is loaded lazily (it is ~1.8 GB)."""

    def __init__(self, model_name: str = EMBED_MODEL, seed: int = config.SEED):
        self.model_name = model_name
        self.pca = PCA(N_COMPONENTS, random_state=seed)
        self.lang_means: dict[str, np.ndarray] = {}   # per-language centre of the fitted books
        self._model = None

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k != "_model"} | {"_model": None}

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            device = embed_device()
            self._model = SentenceTransformer(local_model_path(self.model_name), device=device)
            self._model.max_seq_length = MAX_SEQ
            if device == "cuda":
                self._model.half()   # fp16 fits a 4 GB GPU; checked against the CPU result (docs/accuracy_plan.md)
        return self._model

    def raw(self, token_lists, batch_size: int = 32, progress: bool = False) -> np.ndarray:
        doc_chunks = [chunks_of(t) for t in token_lists]
        flat = [c for cs in doc_chunks for c in cs]
        emb = self.model.encode(flat, batch_size=batch_size, normalize_embeddings=True,
                                show_progress_bar=progress, convert_to_numpy=True)
        out, i = [], 0
        for cs in doc_chunks:
            out.append(emb[i:i + len(cs)].mean(axis=0) if cs else np.zeros(emb.shape[1], np.float32))
            i += len(cs)
        return normalize(np.vstack(out))

    def fit_centring(self, E: np.ndarray, langs) -> None:
        langs = np.asarray(langs)
        self.lang_means = {l: E[langs == l].mean(axis=0) for l in np.unique(langs) if (langs == l).sum() >= 20}

    def resolve_languages(self, E: np.ndarray, langs=None, scripts=None) -> list:
        """The language each row is centred by. A known language is used as given. Otherwise the row takes
        the language whose centre it is closest to (cosine), among the languages of its script if known:
        multilingual embeddings separate languages very clearly, which is why they need centring."""
        means = getattr(self, "lang_means", {})
        out = []
        for i, e in enumerate(E):
            l = langs[i] if langs is not None else None
            if l in means:
                out.append(l)
                continue
            s = scripts[i] if scripts is not None else None
            cands = [k for k in means if s is None or config.LANGUAGES.get(k, {}).get("script") == s] or list(means)
            out.append(max(cands, key=lambda k: float(e @ means[k]) / (np.linalg.norm(means[k]) + 1e-12)) if cands else None)
        return out

    def centre(self, E: np.ndarray, langs=None, scripts=None) -> np.ndarray:
        """Remove each book's language offset so groups follow content, not the language it is written in."""
        means = getattr(self, "lang_means", {})
        if not means:
            return E
        E = E.copy()
        for i, l in enumerate(self.resolve_languages(E, langs, scripts)):
            if l is not None:
                E[i] -= means[l]
        return normalize(E)

    def fit_transform_raw(self, E: np.ndarray, langs=None) -> np.ndarray:
        if CENTRE_BY_LANGUAGE and langs is not None:
            self.fit_centring(E, langs)
            E = self.centre(E, langs)
        return normalize(self.pca.fit_transform(E)).astype(np.float32)

    def transform_raw(self, E: np.ndarray, langs=None, scripts=None) -> np.ndarray:
        return normalize(self.pca.transform(self.centre(E, langs, scripts))).astype(np.float32)

    def transform(self, token_lists, langs=None, scripts=None) -> np.ndarray:
        return self.transform_raw(self.raw(token_lists), langs, scripts)


def load_inputs():
    docs = pd.read_csv(PROCESSED / "docs.csv").set_index("identifier")
    rows = [json.loads(l) for l in (PROCESSED / "tokens.jsonl").open(encoding="utf-8")]
    ids = [r["identifier"] for r in rows]
    toks = [r["tokens"] for r in rows]
    language = docs.loc[ids, "ocr_model"].tolist()   # eng, hin, san, ...
    split = docs.loc[ids, "split"].tolist()
    return ids, toks, language, split


def raw_embeddings(fs: str, ids: list[str], toks) -> np.ndarray:
    """Chunk embeddings averaged per book, before PCA. Cached per model and corpus (no fitting here)."""
    cache = PROCESSED / f"embeddings_raw_{fs}.npy"
    cache_ids = PROCESSED / f"embeddings_ids_{fs}.json"
    if cache.exists() and cache_ids.exists() and json.loads(cache_ids.read_text()) == ids:
        return np.load(cache)
    E = Embedder(MODELS[fs]).raw(toks, progress=True)
    np.save(cache, E)
    cache_ids.write_text(json.dumps(ids))
    return E


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=["A", *MODELS])
    ap.add_argument("--fit", choices=["train", "all"], default="all")
    args = ap.parse_args(argv)
    ids, toks, languages, split = load_inputs()
    fit = np.array([args.fit == "all" or s == "train" for s in split])
    fit_ids = [i for i, f in zip(ids, fit) if f]
    hold_ids = [i for i, f in zip(ids, fit) if not f]
    fit_toks = [t for t, f in zip(toks, fit) if f]
    hold_toks = [t for t, f in zip(toks, fit) if not f]
    out_path = PROCESSED / "features.joblib"
    bundle = joblib.load(out_path) if out_path.exists() else {}
    if bundle.get("ids") != fit_ids or bundle.get("fit") != args.fit:
        bundle = {}  # corpus or fit set changed: recompute everything
    bundle.update({"ids": fit_ids, "fit": args.fit})
    bundle.setdefault("holdout", {})["ids"] = hold_ids
    print(f"fit on {len(fit_ids)} books ({args.fit}); {len(hold_ids)} held out", flush=True)
    if args.only in (None, "A"):
        lsa = TfidfLSA()
        Z, Xw = lsa.fit_transform(fit_toks, [l for l, f in zip(languages, fit) if f])
        bundle["A"] = {"Z": Z, "Xw": Xw, "transform": lsa,
                       "explained_variance": float(lsa.svd.explained_variance_ratio_.sum()),
                       "n_stopwords": len(lsa.stop),
                       "vocab_word": len(lsa.word.vocabulary_), "vocab_char": len(lsa.char.vocabulary_)}
        if hold_toks:
            bundle["holdout"]["A"] = lsa.transform(hold_toks)[0]
        print(f"A: {Z.shape}, SVD explains {bundle['A']['explained_variance']:.1%} of TF-IDF variance, "
              f"{len(lsa.stop)} per-language stopwords", flush=True)
    for fs in MODELS:
        if args.only not in (None, fs):
            continue
        E = raw_embeddings(fs, ids, toks)
        emb = Embedder(MODELS[fs])
        lang = np.asarray(languages)
        Z = emb.fit_transform_raw(E[fit], lang[fit])
        bundle[fs] = {"Z": Z, "transform": emb, "explained_variance": float(emb.pca.explained_variance_ratio_.sum()),
                      "centred_by_language": bool(emb.lang_means)}
        if hold_toks:
            bundle["holdout"][fs] = emb.transform_raw(E[~fit], lang[~fit])
        print(f"{fs}: {Z.shape}, PCA keeps {bundle[fs]['explained_variance']:.1%} of embedding variance", flush=True)
    joblib.dump(bundle, out_path)


if __name__ == "__main__":
    # Run through the importable module so pickled classes are saved as pipeline.features.*,
    # not __main__.*, and can be loaded by the study, the export and the web app.
    from pipeline.features import main as _main
    _main()
