FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt \
 && chmod +x /usr/local/lib/python3.10/site-packages/copilot/bin/copilot 2>/dev/null || true

COPY app.py /app/app.py

ENTRYPOINT ["python", "/app/app.py"]
