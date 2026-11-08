# Throwaway renderer: .docx/.pptx -> PDF -> page images, to check the deliverables by eye.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer libreoffice-impress poppler-utils fonts-dejavu fonts-noto-core fonts-liberation2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /w
