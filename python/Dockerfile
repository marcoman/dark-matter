# ---- Build stage: install dependencies ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY python/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Run stage: minimal image ----
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/root/.local/bin:$PATH"

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application
COPY python/app.py python/
COPY python/templates/ python/templates/
COPY python/static/ python/static/

EXPOSE 5000

CMD ["python", "python/app.py"]
