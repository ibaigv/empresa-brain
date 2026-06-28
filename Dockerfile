FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema mínimas para sentence-transformers / torch CPU
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY brain ./brain

# Descarga el modelo de embeddings en la imagen para que el primer arranque sea rápido
ENV EMBEDDING_MODEL=intfloat/multilingual-e5-small
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

EXPOSE 8000
CMD ["python", "-m", "brain.run"]
