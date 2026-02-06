FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    # Chromium dependencies for Playwright
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libasound2 libxshmfence1 libx11-xcb1 libxcb1 \
    libxext6 libxfixes3 libx11-6 libdbus-1-3 libgtk-3-0 \
    fonts-unifont fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

COPY . .

RUN mkdir -p /app/data/raw /app/data/processed

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
