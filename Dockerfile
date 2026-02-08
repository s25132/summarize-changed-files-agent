FROM python:3.10-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node.js + npm (LTS 20)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copilot CLI (komenda "copilot")
RUN npm install -g @github/copilot

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r /app/requirements.txt

# Szybki sanity check podczas builda:
RUN which git && git --version \
 && which node && node --version \
 && which copilot && copilot --version

RUN chmod +x /usr/local/lib/python3.10/site-packages/copilot/bin/copilot \
 && ls -l /usr/local/lib/python3.10/site-packages/copilot/bin/copilot

COPY app.py /app/app.py

ENTRYPOINT ["python", "/app/app.py"]
