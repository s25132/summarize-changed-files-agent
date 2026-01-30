FROM python:3.10-slim

WORKDIR /app
COPY app.py /app/app.py

ENTRYPOINT ["python", "/app/app.py"]
