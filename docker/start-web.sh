#!/bin/sh
set -eu

echo "Applying database migrations..."

attempt=1
max_attempts=30

while [ "$attempt" -le "$max_attempts" ]; do
  if python manage.py migrate --noinput; then
    echo "Migrations applied successfully."
    break
  fi

  if [ "$attempt" -eq "$max_attempts" ]; then
    echo "Migration failed after ${max_attempts} attempts."
    exit 1
  fi

  echo "Migration attempt ${attempt}/${max_attempts} failed; retrying in 2s..."
  attempt=$((attempt + 1))
  sleep 2
done

exec supervisord -c /app/supervisord.conf
