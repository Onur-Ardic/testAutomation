FROM python:3.12-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node bağımlılıkları (Playwright CLI için)
COPY package.json .
RUN npm install && npx playwright install --with-deps chromium

# Kaynak kodu
COPY . .

# Klasörleri hazırla
RUN mkdir -p tests/generated reports

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
