SHELL := /bin/bash

.PHONY: install dev build lint type-check docker-up docker-down docker-build migrate makemigrations loaddata schema seed-dev-data seed-demo-data

install:
	pnpm install

dev:
	pnpm dev

build:
	pnpm build

lint:
	pnpm lint

type-check:
	pnpm type-check

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose up --build -d

migrate:
	docker compose run --rm backend python manage.py migrate

makemigrations:
	docker compose run --rm backend python manage.py makemigrations

loaddata:
	docker compose run --rm backend python manage.py loaddata roles

schema:
	docker compose run --rm backend python manage.py spectacular --file /app/schema.yaml --validate

seed-dev-data:
	docker compose run --rm backend python manage.py seed_dev_data

seed-demo-data:
	docker compose run --rm backend python manage.py seed_demo_data
