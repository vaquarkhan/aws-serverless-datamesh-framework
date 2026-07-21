# Serverless Data Mesh — control center / CLI image
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="serverless-data-mesh" \
      org.opencontainers.image.description="Proof-gated serverless data mesh (Vaquar Pattern / PVDM)" \
      org.opencontainers.image.source="https://github.com/vaquarkhan/aws-serverless-datamesh-framework" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

# System deps for scientific wheels when needed
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md PYPI.md LICENSE VERSION ./
COPY src ./src
COPY docs ./docs
COPY examples ./examples
COPY schemas ./schemas

RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir .

# Pre-generate northstar mesh for the default UI
RUN serverless-data-mesh apply \
      --contract examples/medallion-e2e/northstar.mesh.yaml \
      --output /data/generated \
    && mkdir -p /data

ENV SDM_UI_PATH=/data/generated \
    PYTHONUNBUFFERED=1

EXPOSE 8765

# Default: mesh control center (override CMD for CLI demos)
CMD ["serverless-data-mesh", "ui", "--path", "/data/generated", "--host", "0.0.0.0", "--port", "8765"]
