# Presentations Django Workspace

This repo holds a skeleton Django project named `presentations`. It matches the default layout created by `django-admin startproject` so you can drop in your own apps.

## Getting started
1. `python3 -m venv .venv` — create a virtual environment in the repo root.
2. `source .venv/bin/activate` — activate the environment (use the appropriate shell for you).
3. `pip install -r requirements.txt` — install Django, MongoEngine, Celery, and dotenv helpers; this requires PyPI access.
4. `python manage.py migrate` — create the configured database schema through Django’s ORM.
5. `python manage.py runserver` — start the development server at `http://127.0.0.1:8000/`.

## Environment
- Copy `.env.example` to `.env` (ignored by git) and keep secrets/config there.
- Populate `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, plus the relational database keys (`DJANGO_DB_ENGINE`, `DJANGO_DB_NAME`, `DJANGO_DB_USER`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT`) before running the project.
- Defaults use SQLite (`DJANGO_DB_ENGINE=django.db.backends.sqlite3`, `DJANGO_DB_NAME=db.sqlite3`); switch to another backend (Postgres/MySQL/etc.) by changing the engine and providing the proper credentials.
- Provide Mongo settings (`MONGO_DB_NAME`, `MONGO_ALIAS`, `MONGO_HOST`, `MONGO_PORT`, `MONGO_USER`, `MONGO_PASSWORD`, `MONGO_AUTH_SOURCE`, or a full `MONGO_URI`). `presentations/settings.py` automatically calls `mongoengine.connect()` using those values.

## MongoEngine
- Define MongoDB documents via `mongoengine.Document` in any module; the connection alias defaults to `MONGO_ALIAS` (default: `default`), so you can simply `from mongoengine import Document`.
- Mongo data models live outside Django’s relational `DATABASES` system, but you can still use Django apps (admin/auth) backed by the configured `DJANGO_DB_ENGINE`.

## Notes
- Update `presentations/settings.py` to change `SECRET_KEY`, `ALLOWED_HOSTS`, or database settings before deploying.
- Add apps to `INSTALLED_APPS` and map URLs inside `presentations/urls.py`.
- Keep `.venv/`, temporary files, and `db.sqlite3` out of version control (already covered in `.gitignore`).
- Keep `.env` outside of version control; use `.env.example` as a template and store the real file securely.
- Start a Celery worker with `celery -A presentations worker --loglevel=info` (remember to set `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` or rely on the default Redis URL). 
- Use the new `presentations_app` to create presentations: POST JSON to `/api/presentations/` with `topic`, `language`, `slides_amount`, and `audience` (optional `author`, `files`, and `status` follow the shared `PresentationDocument` shape), or extend `CreatePresentationCommandDto` for richer create logic.
