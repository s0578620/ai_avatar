FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && apt-get upgrade -y openssl libssl3 \
    && rm -rf /var/lib/apt/lists/* \

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services ./services

CMD ["celery", "-A", "services.worker.worker.tasks", "worker", "--loglevel=INFO", "--concurrency=1"]
