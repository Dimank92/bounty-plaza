FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pytest lxml

COPY . .

EXPOSE 50051

HEALTHCHECK --interval=5s --timeout=5s --start-period=2s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "middleware.sila2_bridge"]
