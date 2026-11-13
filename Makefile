# Territórios com Sede — comandos principais. Ver CLAUDE.md.
UF ?=
UV := uv
NPM := npm --prefix site

.PHONY: setup lint test data build dev e2e clean

setup:
	$(UV) sync
	$(NPM) ci

lint:
	$(UV) run ruff check pipeline
	$(UV) run ruff format --check pipeline
	$(NPM) run check

test:
	$(UV) run pytest -q
	$(NPM) test

data:
	$(UV) run python -m pipeline.run $(if $(UF),--uf $(UF),)

build:
	$(NPM) run build

dev:
	$(NPM) run dev

e2e:
	$(NPM) run e2e

clean:
	rm -rf site/dist site/.astro
