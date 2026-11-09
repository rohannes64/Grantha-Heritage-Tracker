# Grantha: the runnable app (API + website).
# Contains: Tesseract 5 with the 8 study languages, the trained model bundle, the study results,
# the website, and the chosen sentence-embedding model if it runs locally. No page scans are included.
# With the Gemini encoder (feature set G) a check needs internet and GEMINI_API_KEY, which docker compose
# passes in at run time from .env (.env is in .dockerignore, so it never enters the image).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_THREAD_LIMIT=1 \
    HF_HOME=/tmp/hf \
    HERITAGE_MODEL_DIR=/srv/data/model/models \
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

# The export step puts the chosen embedding model in data/model/models/ as a plain folder (not the
# symlinked Hugging Face cache). --chown on each COPY, not a later `chown -R`, which would copy
# the model into a second layer.
RUN useradd --create-home --uid 10001 reader
COPY --chown=reader pipeline /srv/pipeline
COPY --chown=reader app /srv/app
COPY --chown=reader web /srv/web
COPY --chown=reader data/model /srv/data/model
USER reader

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
