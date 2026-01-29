SHELL := /bin/bash
.PHONY: help install migrate makemigrations run shell test
.PHONY: secretkey addmodule refresh-module

help:
	@printf "install       Install dependencies from requirements.txt\n"
	@printf "migrate       Apply migrations to the default database\n"
	@printf "makemigrations Create new migrations for apps\n"
	@printf "run           Start Django development server\n"
	@printf "shell         Open Django shell\n"
	@printf "test          Run Django tests\n"

install:
	pip3 install -r requirements.txt

migrate:
	python3 manage.py migrate

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

secretkey:
	python3 - <<'PY'
	from django.core.management.utils import get_random_secret_key
	print(get_random_secret_key())
	PY

refresh-module:
	pip uninstall -y presentations || true
	pip install -e /Users/riskyworks/Documents/work/presentations/presentations-module
