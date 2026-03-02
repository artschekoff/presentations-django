SHELL := /bin/bash
.PHONY: help install migrate makemigrations run shell test run-all lint kill
.PHONY: buildx-init build-amd64 build-amd64-push
.PHONY: secretkey addmodule refresh-module

help:
	@printf "install       Install dependencies from requirements.txt\n"
	@printf "migrate       Apply migrations to the default database\n"
	@printf "makemigrations Create new migrations for apps\n"
	@printf "run           Start Django development server\n"
	@printf "shell         Open Django shell\n"
	@printf "test          Run Django tests\n"
	@printf "run-all       Start Celery worker and ASGI server\n"
	@printf "lint          Run pylint on project source files\n"
	@printf "buildx-init   Create and select buildx builder\n"
	@printf "build-amd64   Build linux/amd64 image and load locally\n"
	@printf "build-amd64-push Build linux/amd64 image and push to registry\n"

PYTHON ?= .venv/bin/python3
CELERY_CONCURRENCY ?= 6

REGISTRY ?= ghcr.io/artschekoff
IMAGE ?= presentations-django
TAG ?= latest
FULL_IMAGE ?= $(REGISTRY)/$(IMAGE):$(TAG)

install:
	pip3 install -r requirements.txt

makemigrations:
	python3 manage.py makemigrations

run:
	python3 manage.py runserver

shell:
	python3 manage.py shell

createsuperuser:
	python3 manage.py createsuperuser

migrate:
	python3 manage.py migrate

test:
	python3 manage.py test

lint:
	$(PYTHON) -m pylint presentations presentations_app

kill:
	@lsof -ti :8000 | xargs kill -9 2>/dev/null || true
	@pkill -f "celery.*presentations" 2>/dev/null || true
	@pkill -f "daphne.*presentations" 2>/dev/null || true
	@pkill -f "manage.py" 2>/dev/null || true
	@echo "Done"

run-all:
	@bash -c 'set -euo pipefail; \
	$(PYTHON) -m celery -A presentations worker -l info --concurrency=$(CELERY_CONCURRENCY) & CELERY_PID=$$!; \
	$(PYTHON) -m daphne -b 0.0.0.0 -p 8000 presentations.asgi:application & DAPHNE_PID=$$!; \
	trap "kill $$DAPHNE_PID 2>/dev/null; kill $$CELERY_PID 2>/dev/null" EXIT; \
	wait $$DAPHNE_PID'

secretkey:
	python3 - <<'PY'
	from django.core.management.utils import get_random_secret_key
	print(get_random_secret_key())
	PY

refresh-module:
	pip uninstall -y presentations-module || true
	pip install /Users/riskyworks/Documents/work/presentations/presentations-module

buildx-init:
	docker buildx create --use --name multiarch

build-amd64:
	docker buildx build --platform linux/amd64 -t $(FULL_IMAGE) --load --no-cache .

build-amd64-push:
	docker buildx build --platform linux/amd64 -t $(FULL_IMAGE) --push --no-cache .

deploy:
	wget -qO- https://docker.nftwitting.com/api/deploy/compose/eB6AM2XrQE5Gv_H501-xM