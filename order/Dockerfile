FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ORDER_DB_PATH=/data/orders.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py database.py ./

RUN mkdir -p /data

EXPOSE 5002

CMD ["python", "app.py"]
