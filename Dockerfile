FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        supervisor \
        git \
        ghostscript \
        fonts-dejavu \
        fonts-liberation \
        fonts-noto \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
        fontconfig \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
COPY presentations-module /app/presentations-module
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

RUN playwright install-deps chromium
RUN playwright install chromium

COPY . /app
RUN chmod +x /app/docker/start-web.sh

EXPOSE 8000

CMD ["/app/docker/start-web.sh"]
