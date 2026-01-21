FROM python:3.10-slim

WORKDIR /app

# Gerekli sistem paketlerini yükle
# locale-gen ve curl gerekebilir
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Türkçe locale ayarla
RUN sed -i '/tr_TR.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen
ENV LANG tr_TR.UTF-8
ENV LANGUAGE tr_TR:tr
ENV LC_ALL tr_TR.UTF-8

# Kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kaynak kodları kopyala
COPY src/ /app/src/
COPY .env.example /app/.env.example

# Environment variable (Docker içinde çalışırken)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Başlat
CMD ["python", "src/main.py"]
