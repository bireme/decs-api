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
asserting values pinned to stable DeCS records.

Environment variables: `DECS_TEST_ES`, `DECS_TEST_URL` (default `http://localhost:8000`),
`DECS_TEST_TIMEOUT`, `DECS_TEST_USER_AGENT`.

> Layer 3 fails wholesale if the index holds empty documents — run
> `make dev_search_index_build` against the cluster in `ELASTICSEARCH_HOST` first, and see
> `docs/elasticsearch.md`.

### Parity between deployments

`scripts/parity_check.py` is **not** part of the suite. It asserts nothing about content —
it fetches a fixed matrix of requests from two deployments, in **both XML and JSON**, and
reports whether the responses are identical. Run it before a release to confirm the test
environment answers exactly like production:

```
make dev_test_parity PARITY_ARGS="--base-a https://decs-api.teste.bvsalud.org"
```

Both bases default to the environment variables layer 3 uses — `DECS_TEST_URL`
(`http://localhost:8000`) for A and `DECS_TEST_PARITY_URL` (`https://decs-api.bvsalud.org`)
for B — and are overridable with `--base-a` / `--base-b`. It exits non-zero if any
comparison fails.

Comparison is strict by default; the XML `date` stamp is the only field ignored. When the
two indexes are knowingly out of sync, `--ignore-order` compares result lists by `mfn`/`id`
instead of by position, `--ignore-count` compares only the records both returned, and
`--relaxed` is both. Also useful: `--format xml|json|both`, `--case NAME`, `--path PREFIX`,
`--list`, and `-v` for whole diffs instead of the first 40 lines.

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
