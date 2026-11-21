FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/visiooo
COPY requirements.lock requirements.production.txt ./
RUN pip install --no-cache-dir -r requirements.production.txt
COPY card.schema.json ./
COPY app ./app
RUN DEBUG=true SERVE_STATIC=true python app/manage.py collectstatic --noinput \
    && useradd --uid 10001 --create-home visiooo \
    && mkdir -p app/private-media \
    && chown -R visiooo:visiooo app/private-media
USER visiooo
WORKDIR /srv/visiooo/app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
