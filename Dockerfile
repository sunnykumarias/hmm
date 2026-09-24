FROM python:3.12-slim
RUN apt-get update && apt-get install -y tor && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && python -m playwright install --with-deps chromium
COPY insta_worker.py .
CMD python insta_worker.py --worker-id $WORKER_ID
