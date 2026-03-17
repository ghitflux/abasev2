FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements /tmp/requirements
RUN pip install --no-cache-dir -r /tmp/requirements/development.txt

COPY backend /app

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
