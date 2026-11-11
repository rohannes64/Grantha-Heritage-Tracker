# Grantha Heritage Tracker (SIH26096)

Groups unindexed heritage book scans by topic without labels, and lets a new page be checked
against those groups. Real data: 3,000 books from the Digital Library of India scans on the
Internet Archive, in English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada and Tamil.

- **Methods:** hierarchical clustering (Ward, average, complete) and DBSCAN on the same books,
  Euclidean vs Manhattan distance, PCA, silhouette, bootstrap stability.
- **Features compared:** TF-IDF + LSA (word weights) and Gemini Embedding 001 (meaning), with each
  language's average position removed so books group by topic, not by language. The encoder was
  chosen from five (LaBSE, IndicSBERT, BGE-M3, multilingual-E5, Gemini) by a test fixed in advance
  ([docs/accuracy_plan.md](docs/accuracy_plan.md)).
- **App:** upload a page image or PDF (or paste text); get the closest group from both methods,
  how sure the match is, other groups it is also close to, the five nearest archive books, and the
  page's place on the PCA map. It abstains when the OCR is too weak to judge.
- **Accuracy on unseen test books** (measured once): the group predicts a book's subject 58.7% of the
  time against 48.0% for the best simple guess; a single page lands with its own book's group 72.5% of
  the time (82.5% counting "also close to" tags). Details: [docs/evaluation_log.md](docs/evaluation_log.md).

Team: Rajith Sundar (data and OCR), Etikala Sai Pranav (clustering study), Vemuri Rohan (app and delivery).
Plan: [PLAN.md](PLAN.md). Report, deck, viva notes and paper draft: [docs/](docs/).

## The Gemini key

The topic model runs on Google's Gemini API, so the app and the embedding step need internet and a
key. Put it in a file named `.env` in this folder (git- and docker-ignored; never commit it):

```text
GEMINI_API_KEY=your-key-here
```

`docker compose` passes it to the app at run time; the pipeline reads it from the same file. Without
it the app still serves the study and browse pages, and the check page answers that it cannot reach
the topic service.

## Run the app

Needs Docker. A fresh clone has everything the app needs: the fitted model is committed at
`data/model/bundle.joblib` (48 MB) and the website data at `web/data/`. The rest of `data/` (harvested
books, OCR text, caches) is not in the repository; it is only needed to reproduce the study.

```bash
git clone https://github.com/rohannes64/Grantha-Heritage-Tracker.git
cd Grantha-Heritage-Tracker
docker compose up --build
```

Add the `.env` file first (see above) if you want the check page to work. Open http://localhost:8000.
The image (about 1.1 GB) holds Tesseract with the 8 languages, the fitted model, the study results and
the website. API docs: http://localhost:8000/docs.

## Reproduce the study

Every step runs in the pipeline image (Python 3.12, Tesseract 5, scikit-learn, sentence-transformers).
The working folder is mounted, so results land in `data/`, `reports/` and `web/data/`.

```bash
docker compose --profile pipeline build pipeline
docker compose run --rm pipeline python -m pytest -q
```

Harvest (on the host or in the image; resumable, polite: one request start per second per language):

```bash
bash scripts/harvest_all.sh
```

Then, in order (or `bash scripts/run_study.sh`):

```bash
docker compose run --rm pipeline python -m pipeline.ocr --workers 11
docker compose run --rm pipeline python -m pipeline.ocr --ingest
docker compose run --rm pipeline python -m pipeline.fulltext
docker compose run --rm pipeline python -m pipeline.quality
docker compose run --rm pipeline python -m pipeline.preprocess
docker compose run --rm pipeline python -m pipeline.features --fit train
docker compose run --rm pipeline python -m pipeline.study
docker compose run --rm pipeline python -m pipeline.evaluate --split val
docker compose run --rm pipeline python -m pipeline.evaluate --split test
docker compose run --rm pipeline python -m pipeline.features --fit all
docker compose run --rm pipeline python -m pipeline.study
docker compose run --rm pipeline python -m pipeline.sensitivity
docker compose run --rm pipeline python -m pipeline.encoders
docker compose run --rm pipeline python -m pipeline.export
docker compose run --rm pipeline python -m pipeline.figures
docker compose build app
```

The test split is meant to be evaluated once, after every choice has been made on train and
validation books (docs/evaluation_plan.md).

| Step | What it does | Output |
|---|---|---|
| harvest | sampling frame per language (published up to 1960 or undated), seeded draw stratified by era, 5 body pages per book | `data/corpus.sqlite`, `data/pages/` |
| ocr | orientation and script detection, Tesseract with the book's language model; if detection disagrees with the catalogue, the model that reads with higher confidence wins | `data/ocr/*.json` |
| fulltext | the archive's own whole-book OCR text, where it exists | `data/fulltext/` |
| quality | pilot OCR quality per language (first 50 books each) | `reports/pilot_ocr_quality.md` |
| preprocess | multi-script cleaning, field relevance review, imputation, encoding, scaling, readability filter, 60/20/20 train/validation/test split | `data/processed/`, `reports/preprocessing_log.md` |
| features | TF-IDF + LSA, and sentence embeddings (Gemini by default) with per-language centring, 100 dimensions each; `--fit train` or `--fit all` | `data/processed/features.joblib` |
| study | distance study, hierarchical grid, DBSCAN grid, selection, stability, comparison, PCA, profiles | `reports/study/`, `data/processed/study.joblib` |
| evaluate | held-out checks: upload page vs its book, subject accuracy against simple guesses, stability, with and without tags | `reports/eval/`, `docs/evaluation_log.md` |
| sensitivity | the encoded metadata added to the text features at three weights | `reports/study/sensitivity.json` |
| encoders | which encoder carries the most topic information (labelled train+validation books only) | `reports/study/encoder_comparison.json` |
| export | model bundle for the app, study data for the website | `data/model/bundle.joblib`, `web/data/` |
| figures | report figures | `reports/figures/` |

Local encoders (LaBSE, IndicSBERT, BGE-M3) run on a GPU when one is visible (`.venv` with CUDA PyTorch
on the host), else on the CPU. To ship one in the app image, save it as a plain folder under
`data/models/` and build with `--build-arg LOCAL_ENCODER=1`.

On Windows with Git Bash, prefix commands that pass container paths (for example `-e VAR=/work/...`)
with `MSYS_NO_PATHCONV=1`, or Git Bash rewrites them into Windows paths.

## Data and rights

Source: Internet Archive collection `digitallibraryindia`. The catalogue marks these scans' rights as
not available, so the project keeps only OCR text, catalogue fields and links back to the archive.
No page scans are redistributed, including in the Docker image; the website shows page images by
link from the Internet Archive. Book text is sent to Google's Gemini API to be embedded.

## Limits

Printed books, not handwritten manuscripts. OCR quality differs by script. Groups are tendencies named
after their distinctive words and typical books, not subject headings. The topic model is a closed,
online service. Subject labels used for evaluation were made by the project's assistant and await a
team spot-check. See the Study page.
