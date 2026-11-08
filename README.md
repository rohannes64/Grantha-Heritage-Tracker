# Heritage Topic Finder (SIH26096)

Groups unindexed heritage book scans by topic without labels, and lets a new page be checked
against those groups. Real data: 3,000 books from the Digital Library of India scans on the
Internet Archive, in English, Hindi, Sanskrit, Bengali, Gujarati, Telugu, Kannada and Tamil.

- **Methods:** hierarchical clustering (Ward, average, complete) and DBSCAN on the same books,
  Euclidean vs Manhattan distance, PCA, silhouette, bootstrap stability.
- **Features compared:** TF-IDF + LSA (word weights) and LaBSE multilingual sentence embeddings.
- **App:** upload a page image or PDF (or paste text); get the closest group from both methods,
  how sure the match is, the five nearest archive books with shared words, and the page's place
  on the PCA map. It abstains when the OCR is too weak to judge.

Team: Rajith Sundar (data and OCR), Etikala Sai Pranav (clustering study), Vemuri Rohan (app and delivery).
Plan: [PLAN.md](PLAN.md). Report, deck, viva notes and paper draft: [docs/](docs/).

## Run the app

Needs Docker. From this folder:

```bash
docker compose up --build
```

Open http://localhost:8000. The image holds Tesseract with the 8 languages, the trained models,
the study results and the website, and runs offline. API docs: http://localhost:8000/docs.

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

Then, in order:

```bash
docker compose run --rm pipeline python -m pipeline.ocr --workers 11
docker compose run --rm pipeline python -m pipeline.ocr --ingest
docker compose run --rm pipeline python -m pipeline.quality
docker compose run --rm pipeline python -m pipeline.preprocess
docker compose run --rm pipeline python -m pipeline.features
docker compose run --rm pipeline python -m pipeline.study
docker compose run --rm pipeline python -m pipeline.export
docker compose run --rm pipeline python -m pipeline.figures
```

| Step | What it does | Output |
|---|---|---|
| harvest | sampling frame per language (published up to 1960 or undated), seeded draw stratified by era, 5 body pages per book | `data/corpus.sqlite`, `data/pages/` |
| ocr | orientation and script detection, Tesseract with the book's language model; if detection disagrees with the catalogue, the model that reads with higher confidence wins | `data/ocr/*.json` |
| quality | pilot OCR quality per language (first 50 books each) | `reports/pilot_ocr_quality.md` |
| preprocess | multi-script cleaning, field relevance review, imputation, encoding, scaling, readability filter | `data/processed/`, `reports/preprocessing_log.md` |
| features | TF-IDF + LSA and LaBSE embeddings, 100 dimensions each | `data/processed/features.joblib` |
| study | distance study, hierarchical grid, DBSCAN grid, selection, stability, comparison, PCA, profiles | `reports/study/`, `data/processed/study.joblib` |
| export | model bundle for the app, study data for the website | `data/model/bundle.joblib`, `web/data/` |
| figures | report figures | `reports/figures/` |

On Windows with Git Bash, prefix commands that pass container paths (for example `-e VAR=/work/...`)
with `MSYS_NO_PATHCONV=1`, or Git Bash rewrites them into Windows paths.

## Data and rights

Source: Internet Archive collection `digitallibraryindia`. The catalogue marks these scans' rights as
not available, so the project keeps only OCR text, catalogue fields and links back to the archive.
No page scans are redistributed, including in the Docker image; the website shows page images by
link from the Internet Archive.

## Limits

Printed books, not handwritten manuscripts. OCR quality differs by script. Groups are exploratory
patterns named after their most distinctive words, not subject headings. See the Study page.
