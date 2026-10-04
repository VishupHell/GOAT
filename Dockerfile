FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app:create_app

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY run.sh .

RUN useradd --create-home appuser && chmod +x run.sh
USER appuser

EXPOSE 8000
ENTRYPOINT ["./run.sh"]
