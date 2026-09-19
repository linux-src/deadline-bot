FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
COPY wheels/ ./wheels/
RUN pip install --no-cache-dir --no-index --find-links=./wheels -r requirements.txt \
    && rm -rf ./wheels

COPY . .

VOLUME ["/app/data"]

CMD ["python", "bot.py"]
