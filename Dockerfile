FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/tiktok_citations_v3/{audio,images,videos,clips,music,sfx,fonts,history}
RUN mkdir -p /data/tiktok_citations_v3/youtube/{audio,images,videos,clips,thumbnails,history}
RUN mkdir -p /data/tiktok_citations_v3/shorts/{videos,images,audio,history}

RUN cp /app/Montserrat-ExtraBold.ttf /data/tiktok_citations_v3/fonts/ 2>/dev/null || true

EXPOSE 3855

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:3855/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3855", "--workers", "1"]
