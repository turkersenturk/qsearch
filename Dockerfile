FROM python:3.11-slim

# Sistem bağımlılıkları (Docling için gerekli)
RUN apt-get update && apt-get install -y \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Çalışma dizini
WORKDIR /app

# Requirements'ı kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY . .

# Health check için basit bir script
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Varsayılan komut (docker-compose'da override edilecek)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
