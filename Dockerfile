FROM python:3.12-slim

# 1. Instalar Tesseract OCR y el paquete de idioma español
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copiar requirements.txt e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copiar el código fuente de Yakuri
COPY app ./app
COPY scripts ./scripts

# 4. Exponer el puerto dinámico que asigna Render (por defecto 8000)
ENV PORT=8000
EXPOSE 8000

# 5. Iniciar FastAPI inicializando SQLite automáticamente en el lifespan
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]