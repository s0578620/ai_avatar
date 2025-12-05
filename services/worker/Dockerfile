FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services ./services

CMD ["celery", "-A", "services.worker.worker.tasks", "worker", "--loglevel=INFO", "--concurrency=1"]
