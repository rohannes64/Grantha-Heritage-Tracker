# Pipeline image: Python 3.12 + Tesseract 5 with the 8 study languages.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_THREAD_LIMIT=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-osd \
        tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-san tesseract-ocr-ben \
        tesseract-ocr-guj tesseract-ocr-tel tesseract-ocr-kan tesseract-ocr-tam \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
COPY requirements-pipeline.txt requirements-ml.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-pipeline.txt -r /tmp/requirements-ml.txt

# Embedding model cache lives in the bind-mounted data folder during development.
ENV HF_HOME=/work/data/hf

# Code is bind-mounted at /work by docker-compose during development.
CMD ["python", "-m", "pytest", "-q"]
