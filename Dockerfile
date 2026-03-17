# ---- Build stage: install dependencies ----
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
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
COPY app.py .
COPY templates/ templates/
COPY static/ static/

EXPOSE 5000

CMD ["python", "app.py"]
