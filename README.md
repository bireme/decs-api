# decs-api

Requires **Python 3.14**, **Django 5.2 LTS** and **Elasticsearch 9.x**.

1. Intended to be used with database with only tables from decs_portal (from current year edition)
2. Run **python manage.py migrate thesaurus** to create API auxiliary tables (from models_full.py)
3. Run **python manage.py saveauxiliardata** to populate auxiliary tables
4. Run **python manage.py search_index --rebuild  -f --models thesaurus** to create elasticsearch indexes

Each of these has a `make` target — see `make dev_create_aux_tables`,
`make dev_populate_aux_tables` and `make dev_search_index_build`.

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
