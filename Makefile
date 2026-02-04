SHELL := /bin/bash
.PHONY: help install migrate makemigrations run shell test run-all
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
	@printf "buildx-init   Create and select buildx builder\n"
	@printf "build-amd64   Build linux/amd64 image and load locally\n"
	@printf "build-amd64-push Build linux/amd64 image and push to registry\n"

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

run-all:
	@bash -c 'set -euo pipefail; \
	python3 -m celery -A presentations worker -l info & CELERY_PID=$$!; \
	python3 -m daphne -b 0.0.0.0 -p 8000 presentations.asgi:application & DAPHNE_PID=$$!; \
	trap "test -n \"$${DAPHNE_PID:-}\" && kill $$DAPHNE_PID; test -n \"$${CELERY_PID:-}\" && kill $$CELERY_PID" EXIT; \
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
	docker buildx build --platform linux/amd64 -t $(FULL_IMAGE) --load .

build-amd64-push:
	docker buildx build --platform linux/amd64 -t $(FULL_IMAGE) --push .
