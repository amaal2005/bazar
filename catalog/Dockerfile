FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CATALOG_DB_PATH=/data/catalog.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py database.py update_routes.py ./

RUN mkdir -p /data

EXPOSE 5001

CMD ["python", "app.py"]
