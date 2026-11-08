# Heritage Topic Finder: the runnable app (API + website), fully offline once built.
# Contains: Tesseract 5 with the 8 study languages, the trained model bundle, the study results,
# the website, and the LaBSE model. No page scans are included.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_THREAD_LIMIT=1 \
    HF_HOME=/srv/hf \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-osd \
        tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-san tesseract-ocr-ben \
        tesseract-ocr-guj tesseract-ocr-tel tesseract-ocr-kan tesseract-ocr-tam \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements-pipeline.txt requirements-ml.txt requirements-app.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-pipeline.txt -r /tmp/requirements-ml.txt -r /tmp/requirements-app.txt

COPY data/hf /srv/hf
COPY pipeline /srv/pipeline
COPY app /srv/app
COPY web /srv/web
COPY data/model /srv/data/model

RUN useradd --create-home --uid 10001 reader && chown -R reader /srv
USER reader

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
