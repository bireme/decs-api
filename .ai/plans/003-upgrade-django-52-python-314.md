# 003 — Upgrade to Django 5.2 LTS, Python 3.14, current libraries, and uv

## Status

Spec — not started

## Summary

Move the DeCS API off its end-of-life stack (Django 3.2, Python 3.10, Elasticsearch
client 7.15) onto Django 5.2 LTS running on Python 3.14, with every dependency raised to
its current recommended release, and replace pip/requirements.txt with **uv** managing a
`pyproject.toml` + committed `uv.lock`.

The upgrade spans four Django major versions, so it requires removing APIs deleted in
4.0/5.0, and it forces the Elasticsearch client from 7.x to 9.x — which in turn moves the
Elasticsearch server from 8.19 to 9.x.

The API contract must not change. Every endpoint returns responses identical to
production (modulo the result ordering already fixed in features 001/002).

## Goals

- `Django~=5.2.17` (LTS) running on `python:3.14-slim`, container builds and boots clean.
- Dependencies declared in `pyproject.toml` and resolved through a committed `uv.lock`;
  `requirements.txt` / `requirements-dev.txt` removed.
- Container builds via `uv sync --frozen` — fully reproducible, transitive deps included.
- Elasticsearch stack coherent end-to-end: client 9.x against server 9.x.
- No deprecated-API imports remain; `manage.py check` is clean and
  `makemigrations --check --dry-run` reports no model drift.
- Quickterm and term endpoints return responses matching production for a fixed set of
  parity queries.

## Non-goals

- Replacing `jsonfield` with Django's native `models.JSONField`. It backs 35+ columns in
  `app/thesaurus/models_full.py` and is baked into `thesaurus/migrations/0001_initial.py`;
  `jsonfield~=3.2.0` declares Django 5.2 support, so it stays. Defer to its own feature.
- Migrating `django-tastypie` to Django REST Framework.
- Any change to search semantics or ranking (owned by features 001 and 002).
- Adding a test suite (see Verification — parity checking is manual this round).
- Restructuring the repo into an installable package. The project stays a non-packaged
  application with `app/manage.py` where it is.

## Decisions

| Branch | Decision |
| --- | --- |
| Base image | `python:3.14-slim` (Debian), replacing `python:3.10.8-alpine` |
| Package manager | uv, with `pyproject.toml` + committed `uv.lock`; pip removed |
| ES stack | `django-elasticsearch-dsl` 9.0 + `elasticsearch` 9.x client + ES server 9.x |
| jsonfield | Keep (`~=3.2.0`) — native JSONField migration deferred |
| Cleanups | Drop `six`, drop `deform`/`colander`, prune commented-out pins |
| Pinning | Compatible-release ranges (`~=MAJOR.MINOR.PATCH`) in pyproject; exact in `uv.lock` |
| Verification | Manual endpoint parity against production |
| ES rollout | Documented deploy step; index rebuilt from MySQL |

### Why `python:3.14-slim` instead of Alpine

Alpine is musl-based, so PyPI's manylinux wheels don't apply and `mysqlclient` and `lxml`
compile from source on every no-cache build. Debian slim has cp314 manylinux wheels for
both (lxml 6.1.1 and mysqlclient 2.2.8 both publish 3.14 wheels), making builds fast and
reproducible. Cost is roughly 40 MB of image size.

### Why the full ES 9 move

`django-elasticsearch-dsl` 9.0 is the only release declaring Django 5.2 support, and it
requires `elasticsearch>=9,<10`. The 8.x line (`django-elasticsearch-dsl` 8.2) declares
Django only up to 4.2. Note the current repo state is already inconsistent: the pinned
client is 7.15.1 while `docker-compose.yml` runs server 8.19.16 — this upgrade also
resolves that latent mismatch.

### Why `~=` ranges are safe here

Loose ranges would normally hurt reproducibility, but `uv.lock` records the exact resolved
version of every direct and transitive dependency. The ranges express intent (accept
patch/security releases); the lockfile guarantees that any two builds from the same commit
install byte-identical packages.

## Target versions

| Package | Current | Target |
| --- | --- | --- |
| Python | 3.10.8-alpine | 3.14-slim |
| Django | 3.2 | `~=5.2.17` |
| django-tastypie | 0.14.3 | `~=0.15.1` |
| django-elasticsearch-dsl | 7.2.1 | `~=9.0` |
| elasticsearch | 7.15.1 | `~=9.5.0` |
| elasticsearch-dsl | 7.4.0 | *removed* — merged into `elasticsearch.dsl` |
| mysqlclient | 1.4.6 | `~=2.2.8` |
| lxml | 4.6.3 | `~=6.1.1` |
| gunicorn | 20.1.0 | `~=26.0.0` |
| defusedxml | 0.6.0 | `~=0.7.1` |
| jsonfield | 3.1.0 | `~=3.2.0` |
| pyparsing | 3.0.9 | `~=3.3.2` |
| six | 1.16.0 | *removed* (still present transitively via django-elasticsearch-dsl) |
| deform / colander | 2.0.15 / 1.8.3 | *removed* — colander 2.0 caps at Python 3.11 |
| django-debug-toolbar (dev) | 4.0.0 | `~=7.1.0` |
| ES server image | 8.19.16 (prod) / 8.4.3 (dev) | 9.4.4 (both) |

Django 5.2 gained Python 3.14 support in 5.2.8, so `~=5.2.17` is safely above the floor.

## uv migration

### New files

- **`pyproject.toml`** at the repo root:
  - `[project]` with `name = "decs-api"`, `requires-python = ">=3.14"`, and the runtime
    deps from the table above in `dependencies`.
  - `[dependency-groups] dev = ["django-debug-toolbar~=7.1.0"]`, replacing
    `requirements-dev.txt` (currently untracked).
  - No `[build-system]`, plus `[tool.uv] package = false` — this is an application, not a
    distributable package, so uv should not try to build/install the project itself.
- **`uv.lock`** — generated by `uv lock`, committed to the repo.
- **`.python-version`** containing `3.14`, so local `uv run` matches the container.

### Removed files

- `requirements.txt`, `requirements-dev.txt`.

### Dockerfile

- Copy the uv binary from `ghcr.io/astral-sh/uv:latest` (pin to a specific uv version tag)
  rather than `pip install uv`.
- Copy `pyproject.toml` + `uv.lock` first, run `uv sync --frozen --no-install-project`,
  then copy the app — keeping the dependency layer cacheable across code changes.
- Prod stage: `uv sync --frozen --no-dev`. Dev stage: `uv sync --frozen` (includes the
  dev group, which finally makes django-debug-toolbar installable — its install is
  currently commented out in the Dockerfile).
- Set `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`, and put `/app/.venv/bin` on `PATH` so
  `python manage.py ...` and the gunicorn command work unchanged in the compose files.
- `--frozen` makes the build fail loudly if `uv.lock` is stale relative to
  `pyproject.toml`, rather than silently resolving something new.

### Makefile

- Add `deps_lock` (`uv lock`) and `deps_upgrade` (`uv lock --upgrade`) so dependency
  changes go through make, per AGENTS.md.

### Docs

- Update `README.md` for the uv workflow (`uv sync`, `uv add`, `uv run`) and note that
  contributors no longer edit a requirements file by hand.

## Required code changes

### Removed in Django 4.0

- `ugettext_lazy` → `gettext_lazy` in: `thesaurus/field_definitions_desc.py`,
  `field_definitions_qualif.py`, `field_definitions_thesaurus.py`, `choices.py`,
  `models_full.py`, `models_thesaurus.py`, `models_descriptors.py`,
  `models_qualifiers.py`, `admin.py`, and `utils/models.py`.
- `force_text` → `force_str` and `smart_text` → `smart_str`:
  `api/ws_decs_serializer.py:15` (plus call sites at lines 69, 185) and
  `utils/fields.py:5`.

### Removed in Django 5.0

- `USE_L10N = True` in `decs_api/settings.py:138` — delete (localization is always on).

### Long-broken signature

- `utils/fields.py:79` — `MultipleAuxiliaryChoiceField.from_db_value(self, value,
  expression, connection, context)` still carries the `context` argument dropped back in
  Django 3.0. The field has no usages outside `fields.py`, which is why it never surfaced.
  Fix the signature; do not remove the class.

### Elasticsearch client 9

- `elasticsearch_dsl` is now `elasticsearch.dsl`. Update imports in
  `thesaurus/documents.py:3` (`analyzer`, `normalizer`) and
  `api/esearch_functions.py:3` (`Q`, `Search`).
- Verify `analyzer` / `normalizer` / field-class construction in `documents.py` and the
  `Q()` builders in `esearch_functions.py` against the 9.x DSL — especially
  `truncated_word_must()` and the top-2 `match_phrase` logic, which carry the ordering
  semantics fixed in features 001 and 002.

### Elasticsearch client 9 — settings (found during implementation)

- `ELASTICSEARCH_DSL['default']['timeout']` → `'request_timeout'`. elasticsearch-py 8+
  removed `timeout` from the `Elasticsearch()` constructor; leaving it raises
  `TypeError` on the first search and returns HTTP 500 from `/api/thesaurus/quickterm/`.
- `hosts` must carry a scheme in elasticsearch-py 8+; the deployed
  `ELASTICSEARCH_HOST=decs_api_elasticsearch:9200` has none. `settings.py` now prepends
  `http://` when no scheme is present, so existing env files keep working.

### tastypie auto-field (found during implementation)

- tastypie ships no `AppConfig`, so the project's `DEFAULT_AUTO_FIELD = BigAutoField`
  applied to its models while its shipped migrations created `AutoField` columns —
  `makemigrations` wanted to ALTER `tastypie_apikey.id`. Added
  `decs_api.apps.TastypieConfig` pinning tastypie to `AutoField` and referenced it from
  `INSTALLED_APPS`. Pre-existing condition, fixed here to satisfy the no-drift goal.

### six removal

- `api/ws_decs_serializer.py:5, 66, 182` — replace `six.text_type` with `str`, drop the
  import and the dependency.

### deform / colander removal

- The three `field_definitions_*.py` files already have `import colander` / `import deform`
  commented out in the working tree (uncommitted). Delete those commented lines outright.
  **Note:** this feature absorbs those uncommitted working-tree changes.

## Infrastructure changes

### Dockerfile (beyond the uv changes above)

- Base `python:3.14-slim` for all stages.
- Replace the `apk add --virtual .build-deps ...` block with the Debian equivalent:
  build-time `gcc`, `pkg-config`, `default-libmysqlclient-dev`; runtime `libmariadb3`.
  Drop `py3-lxml` — the wheel covers it.
- Remove `pip install "pip<24.1"` — a workaround for legacy package metadata that none of
  the target versions need, and moot once uv owns installation.
- Replace `addgroup -S` / `adduser -S` (busybox) with `groupadd -r` / `useradd -r`.
- Keep the base/dev/prod stage structure and the `appuser` non-root prod user unchanged;
  ensure `/app/.venv` is readable by `appuser`.

### docker-compose

- `docker-compose.yml`: `elasticsearch:8.19.16` → `elasticsearch:9.4.4`.
- `docker-compose-dev.yml`: `elasticsearch:8.4.3` → `elasticsearch:9.4.4`, bringing dev
  and prod into alignment (they currently differ).
- `docker-compose-yazna-dev.yml`: apply the same bump if it pins an ES image.
- Leave `nginx:1.31-alpine` alone — it is current.

### settings.py

- Refresh the doc-comment version references from 3.2 to 5.2 while editing the file.

## Deploy runbook (production)

Index data is fully rebuildable from MySQL via the existing management commands, so the ES
major upgrade needs no migration tooling — just a rebuild:

1. `make prod_stop`
2. Pull the new images; the `esdata` volume may be discarded (contents are derived data).
3. `make prod_start` — bring up ES 9 first, wait for green.
4. `make prod_search_index_build` — rebuild the thesaurus index from MySQL.
5. `make prod_exec_collectstatic`
6. Run the parity queries below against the deployed instance.

## Verification

Per AGENTS.md, all of this runs through `make` targets.

1. `make deps_lock` — `uv.lock` resolves cleanly on Python 3.14 for every pinned range.
   A resolution failure here (most likely tastypie or gunicorn) surfaces before any build.
2. `make dev_build_no_cache && make dev_start` — image builds and container boots.
3. `make dev_sh` → `python manage.py check` (clean) and
   `python manage.py makemigrations --check --dry-run` (no drift — this confirms the
   `jsonfield` and custom-field definitions still deconstruct identically).
4. `make dev_create_aux_tables && make dev_populate_aux_tables`
5. `make dev_search_index_build` — index rebuild against ES 9 succeeds.
6. **Parity check.** For each query below, diff local JSON and XML responses against
   `https://decs-api.bvsalud.org`. Use the cases already documented in
   `docs/quickterm-search-issues.md`, which exercise the ordering and wildcard paths:
   - `quickterm/?query=sindrome respiratoria` (top-2 relevance ordering)
   - `quickterm/?query=sindrome respi*` (multi-word wildcard)
   - `quickterm/?query=transtorno espectro au*` (non-contiguous wildcard match)
   - `quickterm/?query=doenca de cha*`
   - a `thesaurus/term` lookup by DeCS id, in each of `pt-BR`, `es`, `en`
   - one request per serialization format to exercise the lxml/defusedxml XML path
7. Confirm the admin loads (exercises `gettext_lazy` and the custom form fields).

## Risks

- **tastypie on Python 3.14.** 0.15.1 declares Django 5.2 but its Python classifiers stop
  at 3.12. Expected to work, but it is the least-validated pairing here. If it breaks, the
  fallback is `python:3.13-slim` — which keeps every other target version intact.
- **ES 9 DSL surface changes.** The `elasticsearch_dsl` → `elasticsearch.dsl` move is not
  purely a rename across a 7→9 jump; analyzer/normalizer construction and `Q()` shorthand
  need checking. This is the main reason parity testing is mandatory rather than optional.
- **uv is a workflow change for the team.** Anyone rebuilding locally needs uv installed
  (the container carries its own copy). Mitigated by the Makefile targets and README update.
- **Lockfile drift.** `uv sync --frozen` fails the build if someone edits `pyproject.toml`
  without re-running `make deps_lock`. This is the intended behavior — noting it so the
  failure mode is recognized rather than debugged.
- **`gunicorn` 26** classifies only up to Python 3.13; no known 3.14 issue, but worth a
  boot check under the prod stage specifically, not just dev's `runserver`.

## Follow-ups (out of scope)

- Replace `jsonfield` with native `models.JSONField`.
- Add a pytest + pytest-django smoke suite so the next upgrade has automated parity.
