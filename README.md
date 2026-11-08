# Heritage Topic Finder (SIH26096)

Unsupervised topic grouping of heritage documents from the Digital Library of India scans
(Internet Archive mirror), with a web app that checks a new scan against the learned groups.
Full plan: [PLAN.md](PLAN.md).

Team: Rajith Sundar (data & OCR), Etikala Sai Pranav (ML study), Vemuri Rohan (app & delivery).

## Run the pipeline (Docker)

Everything runs in the pipeline image (Python 3.12 + Tesseract 5 with eng, hin, san, ben, guj, tel, kan, tam).

```bash
docker compose build pipeline
docker compose run --rm pipeline python -m pytest -q
docker compose run --rm pipeline python -m pipeline.harvest --stage pilot
docker compose run --rm pipeline python -m pipeline.ocr
docker compose run --rm pipeline python -m pipeline.quality
```

- `harvest`: builds the sampling frame per language (items published up to 1960 or undated),
  draws a seeded sample stratified by era, and downloads 5 body pages per book. Resumable.
- `ocr`: detects orientation and script per page, then OCRs with the model for the detected script.
- `quality`: pilot OCR quality per language, written to `reports/pilot_ocr_quality.md`.

Data lives in `data/` (git-ignored): `corpus.sqlite`, `frame/`, `pages/`, `cache/`.

## Data source and rights

Internet Archive collection `digitallibraryindia`. Only OCR text, metadata and links back to the
archive are kept for the study; page scans are not redistributed.
