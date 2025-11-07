FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY worker ./worker
CMD ["celery", "-A", "worker.tasks", "worker", "--loglevel=INFO", "--concurrency=1"]