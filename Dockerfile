# Reliable Playwright deployment: install Chromium AND its system libraries.
# Using --with-deps works here because Docker builds run as root.
FROM python:3.11-slim

WORKDIR /app

# System basics some wheels need
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Chromium + all OS deps, version-matched to the installed playwright.
RUN python -m playwright install --with-deps chromium

COPY . .

EXPOSE 8501
# $PORT is provided by Render; default to 8501 locally. Shell form so it expands.
CMD streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true
