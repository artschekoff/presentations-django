SHELL := /bin/bash
.PHONY: help install migrate makemigrations run shell test run-all lint kill clean
.PHONY: buildx-init build-amd64 build-amd64-push
.PHONY: secretkey addmodule refresh-module
.PHONY: sync-remote s3-rm-png s3-rm-all s3-ls-complete

-include .env

help:
	@printf "install       Install dependencies from requirements.txt\n"
	@printf "migrate       Apply migrations to the default database\n"
	@printf "makemigrations Create new migrations for apps\n"
	@printf "run           Start Django development server\n"
	@printf "shell         Open Django shell\n"
	@printf "test          Run Django tests\n"
	@printf "run-all       Start Celery worker and ASGI server\n"
	@printf "debug         Start all services with DJANGO_DEBUG=1 and verbose logs\n"
	@printf "lint          Run pylint on project source files\n"
	@printf "buildx-init   Create and select buildx builder\n"
	@printf "build-amd64   Build linux/amd64 image and load locally\n"
	@printf "build-amd64-push Build linux/amd64 image and push to registry\n"
	@printf "s3-rm-png     Remove all *.png files from S3 bucket using .env credentials\n"
	@printf "s3-rm-all     Remove all objects from S3 bucket using .env credentials\n"

PYTHON ?= .venv/bin/python3
CELERY_CONCURRENCY ?= $(if $(PRESENTATIONS_MAX_TABS),$(PRESENTATIONS_MAX_TABS),10)
CELERY_POOL ?= threads

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

clean:
	@echo "Clearing logs..."
	@rm -rf storage/logs/*
	@echo "Clearing generated presentations..."
	@rm -rf storage/generated_presentations/*
	@echo "Flushing database tables..."
	@$(PYTHON) manage.py shell -c "\
from presentations_app.models import Presentation, PresentationLog; \
PresentationLog.objects.all().delete(); \
Presentation.objects.all().delete(); \
print('Done.')"
	@echo "Clean complete."

kill:
	@bash -c 'set -euo pipefail; \
	patterns=( \
	  "celery -A presentations worker" \
	  "celery -A presentations beat" \
	  "daphne .*presentations\.asgi:application" \
	  "manage.py runserver" \
	); \
	for pattern in "$${patterns[@]}"; do \
	  pids=$$(pgrep -f "$$pattern" || true); \
	  if [ -n "$$pids" ]; then \
	    kill $$pids 2>/dev/null || true; \
	  fi; \
	done; \
	sleep 1; \
	for pattern in "$${patterns[@]}"; do \
	  pids=$$(pgrep -f "$$pattern" || true); \
	  if [ -n "$$pids" ]; then \
	    kill -9 $$pids 2>/dev/null || true; \
	  fi; \
	done; \
	pids=$$(lsof -ti tcp:8000 || true); \
	if [ -n "$$pids" ]; then \
	  kill -9 $$pids 2>/dev/null || true; \
	fi; \
	echo "Done"'

run-all:
	@bash -c 'set -euo pipefail; \
	set -a; source .env; set +a; \
	$(PYTHON) -m celery -A presentations worker -l info --pool=$(CELERY_POOL) --concurrency=$(CELERY_CONCURRENCY) & CELERY_PID=$$!; \
	$(PYTHON) -m celery -A presentations beat -l info & BEAT_PID=$$!; \
	$(PYTHON) -m daphne -b 0.0.0.0 -p 8000 --access-log /dev/null presentations.asgi:application & DAPHNE_PID=$$!; \
	trap "kill $$DAPHNE_PID 2>/dev/null; kill $$BEAT_PID 2>/dev/null; kill $$CELERY_PID 2>/dev/null" EXIT; \
	wait $$DAPHNE_PID'

debug:
	@bash -c 'set -euo pipefail; \
	set -a; source .env; set +a; \
	DJANGO_DEBUG=1 \
	$(PYTHON) -m celery -A presentations worker -l debug --pool=$(CELERY_POOL) --concurrency=1 & CELERY_PID=$$!; \
	$(PYTHON) -m celery -A presentations beat -l debug & BEAT_PID=$$!; \
	$(PYTHON) -m daphne -b 0.0.0.0 -p 8000 --access-log /dev/null presentations.asgi:application & DAPHNE_PID=$$!; \
	trap "kill $$DAPHNE_PID 2>/dev/null; kill $$BEAT_PID 2>/dev/null; kill $$CELERY_PID 2>/dev/null" EXIT; \
	wait $$DAPHNE_PID'

secretkey:
	python3 - <<'PY'
	from django.core.management.utils import get_random_secret_key
	print(get_random_secret_key())
	PY

refresh-module:
	pip uninstall -y presentations-module || true
	pip install git+https://github.com/artschekoff/presentations-module.git

buildx-init:
	docker buildx create --use --name multiarch

build-amd64:
	docker buildx build --platform linux/amd64 -t $(FULL_IMAGE) --build-arg CACHEBUST=$$(date +%s) --load .

build-amd64-push:
	docker buildx build --platform linux/amd64 -t $(FULL_IMAGE) --build-arg CACHEBUST=$$(date +%s) --push .

sync-remote:
	mkdir -p storage/remote
	rsync -avz --progress trafficconnect:/home/techcode/gdz/storage/ storage/remote/

s3-rm-png:
	@bash -c 'set -euo pipefail; \
	set -a; source .env; set +a; \
	AWS_ACCESS_KEY_ID="$$AWS_ACCESS_KEY_ID" \
	AWS_SECRET_ACCESS_KEY="$$AWS_SECRET_ACCESS_KEY" \
	aws s3 rm s3://$${S3_BUCKET:-preza.kz}/ \
	  --recursive \
	  --exclude "*" \
	  --include "*.txt" \
	  --endpoint-url "$${S3_ENDPOINT_URL:-https://s3.ru-3.storage.selcloud.ru}" \
	  --no-verify-ssl'

s3-rm-all:
	@bash -c 'set -euo pipefail; \
	set -a; source .env; set +a; \
	AWS_ACCESS_KEY_ID="$$AWS_ACCESS_KEY_ID" \
	AWS_SECRET_ACCESS_KEY="$$AWS_SECRET_ACCESS_KEY" \
	aws s3 rm s3://$${S3_BUCKET:-preza.kz}/ \
	  --recursive \
	  --endpoint-url "$${S3_ENDPOINT_URL:-https://s3.ru-3.storage.selcloud.ru}" \
	  --no-verify-ssl'

s3-ls-complete:
	@bash -c 'set -euo pipefail; \
	set -a; source .env; set +a; \
	AWS_ACCESS_KEY_ID="$$AWS_ACCESS_KEY_ID" \
	AWS_SECRET_ACCESS_KEY="$$AWS_SECRET_ACCESS_KEY" \
	aws s3 ls s3://$${S3_BUCKET:-preza.kz}/ \
	  --recursive \
	  --endpoint-url "$${S3_ENDPOINT_URL:-https://s3.ru-3.storage.selcloud.ru}" \
	  --no-verify-ssl \
	| sed -E "s/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} +[0-9]+ //" \
	| sed "s|/[^/]*$$||" \
	| sort -u \
	| while read -r dir; do \
	    has_pdf=false; has_txt=false; has_pptx=false; \
	    while IFS= read -r file; do \
	      case "$$file" in *.pdf) has_pdf=true;; *.txt) has_txt=true;; *.pptx) has_pptx=true;; esac; \
	    done < <(aws s3 ls "s3://$${S3_BUCKET:-preza.kz}/$$dir/" \
	      --endpoint-url "$${S3_ENDPOINT_URL:-https://s3.ru-3.storage.selcloud.ru}" \
	      --no-verify-ssl \
	    | sed -E "s/^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} +[0-9]+ //"); \
	    if $$has_pdf && $$has_txt && $$has_pptx; then echo "$$dir"; fi; \
	  done | tee s3-complete.txt; \
	echo "Saved $$(wc -l < s3-complete.txt | tr -d " ") folders to s3-complete.txt"'

deploy:
	wget -qO- https://docker.nftwitting.com/api/deploy/compose/eB6AM2XrQE5Gv_H501-xM