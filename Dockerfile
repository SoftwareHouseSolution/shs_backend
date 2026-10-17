FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY . .

# Settings refuse to import without these; build-time placeholders, never used at runtime.
RUN DJANGO_SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db \
    python manage.py collectstatic --noinput

# Fixed uid so the host can chown the bind-mounted media folder to it. /app/media-trash
# holds files set aside by the admin's media clean-up (a volume in compose.yml); created
# here so a new volume inherits the app user's ownership.
RUN useradd --uid 10001 --create-home app \
    && mkdir -p /app/media /app/media-trash \
    && chown app /app/media /app/media-trash
USER app

EXPOSE 8000

# Healthy = the app answers and the database is reachable (GET /api/v1/health/).
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python", "scripts/healthcheck.py"]

# On every start: apply migrations, then index existing media for upload de-duplication
# (only the first time: --if-empty skips once the index exists), then serve.
# One process with threads: the default cache is per-process memory, so a single process
# keeps the content cache and rate limits consistent without adding Redis.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py index_media --if-empty && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 8 --timeout 120 --access-logfile -"]
