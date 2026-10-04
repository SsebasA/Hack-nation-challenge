# SPARK Lab backend: sparklab.api + Omnigent (the agents) in one container.
# Build context: backend/. The code lives in the image; the lab's records live on a volume mounted at /data
# (see deploy/start.sh). Railway: Root Directory = backend, config file = /backend/railway.json.
FROM python:3.13-slim

# git: pre-registrations are committed (hash + commit). safe.directory: the volume may be owned by another uid.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system --add safe.directory '*'

WORKDIR /app/backend

# Omnigent first: the heaviest layer, cached across code changes. Same version the lab was validated with.
RUN pip install --no-cache-dir "omnigent==0.16.0"

# sparklab, editable so its paths (lab.yaml, board/) resolve inside /app/backend.
COPY pyproject.toml ./
COPY sparklab ./sparklab
RUN pip install --no-cache-dir -e ".[api]"

COPY lab.yaml ./
COPY board ./board
COPY docs ./docs
COPY deploy ./deploy

ENV PYTHONUNBUFFERED=1 \
    SPARKLAB_HOME=/data/lab \
    OMNIGENT_DATA_DIR=/data/omnigent \
    OMNIGENT_HOST_NO_OPEN=1 \
    SPARK_API_HOST=0.0.0.0

EXPOSE 8787
CMD ["bash", "deploy/start.sh"]
