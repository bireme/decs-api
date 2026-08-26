IMAGE_NAME=bireme/decs-api
APP_VERSION=$(shell git describe --tags --long --always | sed 's/-g[a-z0-9]\{7\}//')
TAG_LATEST=$(IMAGE_NAME):latest

COMPOSE_FILE_DEV=docker-compose-dev.yml
PACKAGE ?=

## variable used in docker-compose for tag the build image
export IMAGE_TAG=$(IMAGE_NAME):$(APP_VERSION)

tag:
	@echo "IMAGE TAG:" $(IMAGE_TAG)

## docker-compose desenvolvimento
dev_build:
	@docker compose -f $(COMPOSE_FILE_DEV) build

dev_build_no_cache:
	@docker compose -f $(COMPOSE_FILE_DEV) build --no-cache

dev_start:
	@docker compose -f $(COMPOSE_FILE_DEV) up -d

dev_start_api:
	@docker compose -f $(COMPOSE_FILE_DEV) up -d decs_api_app

dev_run:
	@docker compose -f $(COMPOSE_FILE_DEV) up

dev_run_api:
	@docker compose -f $(COMPOSE_FILE_DEV) up decs_api

dev_logs:
	@docker compose -f $(COMPOSE_FILE_DEV) logs -f

dev_stop:
	@docker compose -f $(COMPOSE_FILE_DEV) stop

dev_ps:
	@docker compose -f $(COMPOSE_FILE_DEV) ps

dev_rm:
	@docker compose -f $(COMPOSE_FILE_DEV) rm -f

dev_sh:
	@docker compose -f $(COMPOSE_FILE_DEV) exec decs_api_app sh

dev_create_aux_tables:
	@docker compose -f $(COMPOSE_FILE_DEV) exec decs_api_app python manage.py migrate thesaurus

dev_populate_aux_tables:
	@docker compose -f $(COMPOSE_FILE_DEV) exec decs_api_app python manage.py saveauxiliardata

dev_search_index_build:
	@docker compose exec decs_api_app python manage.py search_index --rebuild -f --models thesaurus

## raise pinned versions within the ranges declared in pyproject.toml
dev_upgrade_package:
	@uv lock $(if $(PACKAGE),--upgrade-package $(PACKAGE),--upgrade)

## tests
## `run --rm` instead of `exec`: the suite needs no running stack and no
## published port, so it works whether or not `make dev_start` has been used
TEST_RUN=docker compose -f $(COMPOSE_FILE_DEV) run --rm --no-deps -T decs_api_app

## layers 1 + 2: no Elasticsearch, no MySQL, no network
dev_test:
	@$(TEST_RUN) python manage.py test --settings=decs_api.settings_test

## layer 3: against real MySQL + Elasticsearch, through a server started in the
## same container (DECS_TEST_URL points elsewhere if you already have one running)
dev_test_live:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm --no-deps -T \
		-e DECS_TEST_ES=1 -e DJANGO_ALLOWED_HOSTS=localhost \
		-v $(CURDIR)/scripts:/scripts decs_api_app \
		sh -c 'python manage.py runserver 0.0.0.0:8000 --noreload >/tmp/server.log 2>&1 & \
		       python /scripts/wait_for_api.py && \
		       python manage.py test api.tests.test_live --settings=decs_api.settings_test'

## parity: diff two deployments, XML and JSON, with no test runner involved.
## Not part of the suite — pass arguments through PARITY_ARGS, e.g.
##   make dev_test_parity PARITY_ARGS="--base-a https://decs-api.teste.bvsalud.org --relaxed"
dev_test_parity:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm --no-deps -T \
		-v $(CURDIR)/scripts:/scripts decs_api_app \
		python /scripts/parity_check.py $(PARITY_ARGS)

## regenerate app/api/tests/fixtures/decs_sample.json from the dev database
dev_dump_test_fixtures:
	@docker compose -f $(COMPOSE_FILE_DEV) run --rm --no-deps -T \
		-v $(CURDIR)/scripts:/scripts decs_api_app python /scripts/dump_test_fixtures.py


## docker-compose prod
prod_build:
	@docker compose build
	@docker tag $(IMAGE_TAG) $(TAG_LATEST)

prod_build_no_cache:
	@docker compose build --no-cache
	@docker tag $(IMAGE_TAG) $(TAG_LATEST)

prod_run:
	@docker compose up

prod_run_api:
	@docker compose up decs_api_app

prod_start:
	@docker compose up -d

prod_stop:
	@docker compose stop

prod_logs:
	@docker compose logs -f

prod_ps:
	@docker compose ps

prod_rm:
	@docker compose rm -f

prod_sh:
	@docker compose exec decs_api_app sh

## force a fresh pull of the nginx image and recreate the webserver container.
## the image tag (nginx:1.30-alpine) is a moving tag, so `pull` is what actually
## brings in the upstream patch releases
prod_upgrade_webserver:
	@docker compose pull decs_api_webserver
	@docker compose up -d --force-recreate decs_api_webserver

prod_exec_collectstatic:
	@docker compose exec -T decs_api_app python manage.py collectstatic --noinput

## layers 1 + 2 inside the running production container
prod_test:
	@docker compose exec -T decs_api_app python manage.py test --settings=decs_api.settings_test

prod_create_aux_tables:
	@docker compose exec decs_api_app python manage.py migrate thesaurus

prod_populate_aux_tables:
	@docker compose exec decs_api_app python manage.py saveauxiliardata

prod_search_index_build:
	@docker compose exec decs_api_app python manage.py search_index --rebuild -f --models thesaurus
