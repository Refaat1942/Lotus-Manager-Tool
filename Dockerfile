FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && rm -rf /var/lib/apt/lists/*

COPY web_app/requirements.txt /app/web_app/requirements.txt
RUN pip install --no-cache-dir -r web_app/requirements.txt

COPY core/ /app/core/
COPY web_app/ /app/web_app/
COPY run_web.py /app/run_web.py

RUN mkdir -p /app/web_app/data /app/web_app/static/uploads

ENV SECRET_KEY=lotus-production-secret-change-me
EXPOSE 16320

CMD ["python", "run_web.py"]
