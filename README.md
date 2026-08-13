# decs-api

Requires **Python 3.14**, **Django 5.2 LTS** and **Elasticsearch 9.x**.

1. Intended to be used with database with only tables from decs_portal (from current year edition)
2. Run **python manage.py migrate thesaurus** to create API auxiliary tables (from models_full.py)
3. Run **python manage.py saveauxiliardata** to populate auxiliary tables
4. Run **python manage.py search_index --rebuild  -f --models thesaurus** to create elasticsearch indexes

Each of these has a `make` target — see `make dev_create_aux_tables`,
`make dev_populate_aux_tables` and `make dev_search_index_build`.

## Tests

The suite has three layers, in increasing order of infrastructure required. Every target
runs inside a container — there is no host-side test command.

| Command | What runs | Needs |
| --- | --- | --- |
| `make dev_test` | Layers 1 + 2 | nothing but Docker |
| `make dev_test_live` | Layer 3 | dev MySQL and a **rebuilt** Elasticsearch index |
| `make dev_test_parity` | Layer 3 plus a diff against production | the above, plus network |
| `make prod_test` | Layers 1 + 2 in the running production container | `make prod_start` |

**Layer 1 — pure unit.** The Elasticsearch query DSL (`get_search_q`), the bool expression
parser (`f_parse`), the set algebra over search results (`complex_search`) and language
resolution. No database, no cluster.

**Layer 2 — endpoints.** The real URLconf, resources, `dehydrate` and serializers, driven
through `django.test.Client` against real DeCS records in an SQLite test database.
Elasticsearch is faked at `execute_simple_search` / `execute_quick_search`, so the tests
assert both the rendered response and the query that would have reached the cluster.

**Layer 3 — live.** Skipped unless `DECS_TEST_ES=1`, which `make dev_test_live` sets. It starts
a server in the container and drives the API over HTTP against the real database and index,
asserting values pinned to stable DeCS records. `DECS_TEST_PARITY=1` additionally fetches
each query from `https://decs-api.bvsalud.org` and reports the first structural difference.

Environment variables: `DECS_TEST_ES`, `DECS_TEST_PARITY`, `DECS_TEST_URL` (default
`http://localhost:8000`), `DECS_TEST_PARITY_URL` (default `https://decs-api.bvsalud.org`).

> Layer 3 fails wholesale if the index holds empty documents — run
> `make dev_search_index_build` against the cluster in `ELASTICSEARCH_HOST` first, and see
> `docs/elasticsearch.md`.

The fixtures are a curated slice of three real records (a descriptor with two tree numbers,
one with pharmacological actions, and a qualifier with both `Q` and `Y` tree numbers) plus
the first level categories. Regenerate them from the dev database with
`make dev_dump_test_fixtures`; the record ids are documented in
`scripts/dump_test_fixtures.py`.

## Dependencies

Dependencies are managed with [uv](https://docs.astral.sh/uv/). They are declared in
`pyproject.toml` and pinned to exact resolved versions in `uv.lock`, which is committed.
There is no `requirements.txt`.

- `uv sync` — create/update the local virtualenv from the lockfile
- `uv add <package>` / `uv remove <package>` — change a dependency
- `uv run python manage.py ...` — run a command inside the environment
- `make deps_lock` — re-lock after editing `pyproject.toml` by hand
- `make deps_upgrade` — raise pinned versions within the ranges in `pyproject.toml`

The Docker build installs with `uv sync --frozen`, which **fails the build if `uv.lock`
is out of date** relative to `pyproject.toml`. If a build fails that way, run
`make deps_lock` and commit the updated lockfile.
