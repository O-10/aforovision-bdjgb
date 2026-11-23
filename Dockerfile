FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    AFORO_ORIGIN=http://127.0.0.1:8000 \
    AFORO_DATA_DIR=/data

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /data

EXPOSE 8000 8001

# El motor corre internamente en 8000; la vista pública usa el puerto que asigne la nube.
CMD ["sh", "-c", "uvicorn server:app --host 127.0.0.1 --port 8000 & uvicorn public_server:app --host 0.0.0.0 --port ${PORT:-8001} & wait"]
