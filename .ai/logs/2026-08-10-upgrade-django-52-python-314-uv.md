# 2026-08-10 — Upgrade to Django 5.2 LTS, Python 3.14, current libraries, and uv

Implements [`.ai/plans/003-upgrade-django-52-python-314.md`](../plans/003-upgrade-django-52-python-314.md)
on branch `feature/upgrade-django-52-python-314-uv`.

## Summary

Moved the API from Django 3.2 / Python 3.10 / Elasticsearch client 7.15 to
Django 5.2.17 LTS / Python 3.14.7 / Elasticsearch 9.5 client against an ES 9.4.4 server,
and replaced pip + `requirements.txt` with uv + `pyproject.toml` + committed `uv.lock`.

## Dependency management (pip → uv)

- Added `pyproject.toml` (runtime deps + `dev` dependency-group), `.python-version`
  (`3.14`), and a committed `uv.lock`.
- Deleted `requirements.txt` and `requirements-dev.txt`.
- `Makefile`: added `deps_lock` and `deps_upgrade`.
- Ranges use `~=MAJOR.MINOR.PATCH` (patch updates only); `uv.lock` supplies exact
  reproducibility, so the loose ranges cost nothing.

## Versions

Django 5.2.17 · django-tastypie 0.15.1 · django-elasticsearch-dsl 9.0 · elasticsearch
9.5.0 · mysqlclient 2.2.8 · lxml 6.1.1 · gunicorn 26.0.0 · defusedxml 0.7.1 · jsonfield
3.2.0 · pyparsing 3.3.2 · django-debug-toolbar 7.1.0 (dev).
Removed: `six`, `deform`, `colander`, `elasticsearch-dsl` (merged into `elasticsearch.dsl`).

`colander` had to go regardless — 2.0 supports Python 3.11 at most.

## Code changes

- `ugettext_lazy` → `gettext_lazy` across 10 modules (removed in Django 4.0).
- `force_text`/`smart_text` → `force_str`/`smart_str`.
- `six.text_type` → `str`; `import six` dropped.
- `USE_L10N` deleted (removed in Django 5.0).
- `utils/fields.py` — dropped the stale `context` argument from
  `MultipleAuxiliaryChoiceField.from_db_value`, removed in Django 3.0. It never broke
  because the field has no callers.
- `elasticsearch_dsl` → `elasticsearch.dsl` in `thesaurus/documents.py` and
  `api/esearch_functions.py`. The legacy top-level module no longer exists in 9.x.
- Removed the commented-out `colander`/`deform` imports from the three
  `field_definitions_*.py` files (absorbed the pending working-tree edits).

### Two problems the plan did not anticipate

1. **`ELASTICSEARCH_DSL['timeout']`** — elasticsearch-py 8+ removed `timeout` from the
   `Elasticsearch()` constructor. It raised `TypeError` on the first search, so
   `/api/thesaurus/quickterm/` returned HTTP 500. Renamed to `request_timeout`.
   Caught only by booting the app and issuing real requests, not by `manage.py check`.
2. **`hosts` needs a scheme** — elasticsearch-py 8+ rejects bare `host:port`, and the
   deployed value is `decs_api_elasticsearch:9200`. `settings.py` now prepends `http://`
   when no scheme is present, so existing env files keep working untouched.

Also fixed a pre-existing condition surfaced by the no-drift goal: tastypie ships no
`AppConfig`, so `DEFAULT_AUTO_FIELD = BigAutoField` applied to its models while its
shipped migrations created `AutoField` columns, making `makemigrations` want to ALTER
`tastypie_apikey.id`. Added `decs_api/apps.py::TastypieConfig` pinning tastypie to
`AutoField` to match the existing database.

## Infrastructure

- `Dockerfile`: `python:3.10.8-alpine` → `python:3.14-slim`; apk build-deps replaced with
  `gcc`, `pkg-config`, `default-libmysqlclient-dev`, `libmariadb3`; uv binary copied from
  `ghcr.io/astral-sh/uv:0.10.0`; installs via `uv sync --frozen` (`--no-dev` for prod);
  busybox `addgroup`/`adduser` → `groupadd`/`useradd`; dropped the `pip<24.1` pin.
- **The venv lives at `/opt/venv`, not `/app/.venv`** — `docker-compose-dev.yml`
  bind-mounts `./app/` over `/app`, which would shadow a venv placed inside it. Dependency
  manifests live in `/deps` for the same reason.
- Elasticsearch image `8.19.16` (prod) and `8.4.3` (dev, yazna-dev) → `9.4.4` everywhere;
  dev and prod were previously on different versions.
- `README.md` documents the uv workflow; `conf/app-env-TEMPLATE` notes the host format.

## Verification

- `uv lock` resolves cleanly on Python 3.14 — retires the plan's main risk (tastypie
  0.15.1 classifies only to 3.12, but installs and runs fine).
- Dev image builds; dependency install takes ~6s with **zero compilation** (all wheels),
  confirming the Debian-slim choice.
- Prod image builds, runs as non-root `appuser`, Python 3.14.7, gunicorn 26.0.0.
- `manage.py check` → **no issues**; `makemigrations --check --dry-run` → **no changes**.
- Against a live **ES 9.4.4** server: all five indices created with the correct
  analyzers (`standard_asciifolding`, `keyword_asciifolding`), the
  `custom_sort_normalizer`, and the `full_field`/`raw`/`sort` subfields.
- Query semantics from features 001/002 verified against real indexed data — asciifolding
  (`sindrome`→"Síndrome", `doenca`→"Doença"), the non-contiguous multi-word wildcard
  (`transtorno espectro au*` → "Transtorno **do** Espectro Autista"), `match_phrase`, and
  byte-order sorting on `term_string.sort`.
- Under gunicorn: `GET /api/thesaurus/term/?id=D000001` → 200 and
  `GET /api/thesaurus/quickterm/?query=teste` → 200.

### Not done

**Response parity against production was not run.** It needs the BIREME MySQL database
(`172.17.1.20`, unreachable from this machine) with real DeCS data. Verification used a
throwaway SQLite DB plus a local ES 9.4.4 with synthetic terms, which exercises every
code path and the ES query semantics but cannot compare real response bodies. Parity
against `https://decs-api.bvsalud.org` remains a required pre-merge step — see the
Verification section of the plan for the query list.

Note for whoever runs it: `api/thesaurus_term_api.py:19` executes a query at *import*
time, so every management command needs populated tables. Pre-existing, not touched here.

## Deploy

ES moves 8.19 → 9.4.4, so the index must be rebuilt. Index data is derived from MySQL, so
no migration tooling is needed: stop the app, replace the ES container (the `esdata`
volume can be discarded), `make prod_search_index_build`, `make prod_exec_collectstatic`,
then run the parity queries. Full runbook in the plan.
