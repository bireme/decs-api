IMAGE_NAME=bireme/decs-api
APP_VERSION=$(shell git describe --tags --long --always | sed 's/-g[a-z0-9]\{7\}//')
TAG_LATEST=$(IMAGE_NAME):latest

COMPOSE_FILE_DEV=docker-compose-dev.yml

## variable used in docker-compose for tag the build image
export IMAGE_TAG=$(IMAGE_NAME):$(APP_VERSION)

tag:
	@echo "IMAGE TAG:" $(IMAGE_TAG)

## docker-compose desenvolvimento
dev_build:
	@docker-compose -f $(COMPOSE_FILE_DEV) build

dev_up:
	@docker-compose -f $(COMPOSE_FILE_DEV) up -d

dev_run:
	@docker-compose -f $(COMPOSE_FILE_DEV) up

dev_logs:
	@docker-compose -f $(COMPOSE_FILE_DEV) logs -f

dev_stop:
	@docker-compose -f $(COMPOSE_FILE_DEV) stop

dev_ps:
	@docker-compose -f $(COMPOSE_FILE_DEV) ps

dev_rm:
	@docker-compose -f $(COMPOSE_FILE_DEV) rm -f

dev_sh:
	@docker-compose -f $(COMPOSE_FILE_DEV) exec decs_api sh
