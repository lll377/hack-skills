FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEMORY_HOST=0.0.0.0 \
    MEMORY_PORT=8765 \
    MEMORY_DB_PATH=/data/memory.db

WORKDIR /app
COPY . /app
RUN useradd --create-home --uid 10001 memory && mkdir /data && chown memory:memory /data

USER memory
EXPOSE 8765
VOLUME ["/data"]
CMD ["python", "run.py"]
