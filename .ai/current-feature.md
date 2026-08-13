# Current Feature: API endpoint test suite

## Status

<!-- Not Started|In Progress|Completed -->

In Progress

## Goals

<!-- Goals & requirements -->

- `make dev_test` passes with no Elasticsearch, no MySQL and no network — the offline suite
  is the default and runs anywhere.
- Every live endpoint and every documented query mode is covered:
  `/api/thesaurus/` (index), `/api/thesaurus/term/` (`words`, `bool`, `tree_id` in its
  first-level / second-level / full-tree forms) and `/api/thesaurus/quickterm/` (`query`),
  each across `ths`, `status`, `lang`, `count`, `$`→`*` and both response formats.
- The generated Elasticsearch query is asserted for every `get_search_q` branch
  (101–107, 401–407, `words`, `quick`, `tree_id`, invalid prefix).
- Responses are validated structurally on parsed XML/JSON — elements, attributes,
  ordering and counts — not by string matching.
- Named regression tests lock the three fixes this branch line shipped: quickterm term
  ordering (plan 001), multi-word wildcard quickterm (plan 002), and the empty-documents
  Elasticsearch bug (`BaseDocument._prepared_fields`).
- `make dev_test_live` passes against the dev stack using pinned values from real DeCS
  records; `DECS_TEST_PARITY=1` additionally diffs against production.
- No API behaviour changes. The only production edit is making `DECS_LANGUAGES` lazy.

## Notes

<!-- Any extra notes -->

Full specification: [`features/001-api-endpoint-test-suite.md`](features/001-api-endpoint-test-suite.md)

**Key decisions**

| Branch | Decision |
| --- | --- |
| Scope | `term` + `quickterm` only (+ API index, schema, 405s) |
| Elasticsearch | Faked at the `execute_*` seam by default; opt-in live layer with real data |
| Query DSL | Verified separately via `get_search_q(...)['query'].to_dict()` |
| Test DB | SQLite in-memory via `decs_api/settings_test.py`, unmanaged models forced managed |
| Fixtures | JSON files dumped from the dev DB by `make dev_dump_test_fixtures` |
| Assertions | Structural — parse XML/JSON, assert elements/attributes/order/counts |
| Live expectations | Pinned real-record values (`DECS_TEST_ES=1`) + optional production diff (`DECS_TEST_PARITY=1`) |
| Runner | Django's built-in runner — no new dependencies |
| Layout | Per-app `tests/` packages |
| Error paths | Characterized as-is; defects logged as follow-ups, not fixed here |
| CI | Make targets only; no GitHub Actions yet |

**Three layers**

1. **Pure unit** (`SimpleTestCase`, no infra) — `f_parse`, `complex_search` set algebra,
   `get_valid_lang`, `truncated_word_must`, and every `get_search_q` branch.
2. **Endpoint tests** (SQLite test DB, ES faked at
   `execute_simple_search` / `execute_quick_search`) — real URLconf → tastypie →
   `dehydrate` → serializer, driven through `django.test.Client`.
3. **Live integration** (opt-in, `DECS_TEST_ES=1`) — real dev MySQL + Elasticsearch,
   pinned assertions from real DeCS records.

**Discovered during spec**

- `app/thesaurus/urls.py` is dead code: it imports `thesaurus.views`, which does not
  exist, and is not included from `decs_api/urls.py`. Explicitly out of scope.
- `api/thesaurus_term_api.py:19-20` runs a DB query at *import* time to build
  `DECS_LANGUAGES`, so language handling depends on when the URLconf was first loaded.
  Made lazy — the one production edit in this feature.
- Most thesaurus models are `managed = False` in `0001_initial.py`, so `migrate` creates
  no tables for `TermListDesc` / `TreeNumbersList*` — which the endpoints read. Test
  settings flip `managed = True` via a `pre_migrate` hook.
- `Makefile`'s `prod_make_test` called `make test`, a target that did not exist (and no
  Docker stage installs `make`). Now `prod_test`, running `manage.py test` directly.

**Follow-up defects (characterized, not fixed here)**

1. `thesaurus_quickterm_api.py:150-151` — unguarded `treeN_list[0]` → `IndexError` when a
   term has no tree number.
2. `thesaurus_term_api.py:372-384` — `full_tree` can be unbound when the requested
   `tree_id` is not one of the record's.
3. `thesaurus_term_api.py:270-274` — `term_string` / `term_string_en` can be unbound when
   no label matches the language.
4. Qualifier labels/synonyms are prefixed with `/` in place, mutating the loaded
   JSONField payload.
5. `thesaurus_term_api.py:166` — unguarded `FirstLevel.objects.get()` → 500 on an unknown
   two-character `tree_id`.
6. Unused imports in both API modules.

**Out of scope**

- Reviving the dead `thesaurus/urls.py` CRUD views.
- Fixing the six defects above — this feature changes no API behaviour.
- Adding pytest or any new dependency.
- CI configuration.

**Main risk**

SQLite/MySQL divergence under the force-managed hook. Validate `migrate
--settings=decs_api.settings_test` early; fallback is running layer 2 inside the dev
container against MySQL.

Per AGENTS.md: use `make` commands throughout, and write an implementation log to
`.ai/logs/` when done.

## Detailed Plan

<!-- Link to detailed plan file -->

[004-api-endpoint-test-suite.md](plans/004-api-endpoint-test-suite.md)

## History

<!-- Keep this updated. Earliest to latest -->

- `.ai/plans/001-fix-ordering-terms-quickterm.md` — fix ordering of terms in quickterm
- `.ai/plans/002-fix-wildcard-multiword-quickterm.md` — fix multi-word wildcard (`*`) search
- 2026-08-10: Starting Upgrade to Django 5.2 LTS, Python 3.14, current libraries, and uv — following plan [003-upgrade-django-52-python-314.md](plans/003-upgrade-django-52-python-314.md)
- 2026-08-12: Starting API endpoint test suite — following spec [001-api-endpoint-test-suite.md](features/001-api-endpoint-test-suite.md)
- 2026-08-12: Starting API endpoint test suite — following plan [004-api-endpoint-test-suite.md](plans/004-api-endpoint-test-suite.md)
- 2026-08-12: Implemented API endpoint test suite on branch `feature/api-endpoint-test-suite` — log [logs/2026-08-12-api-endpoint-test-suite.md](logs/2026-08-12-api-endpoint-test-suite.md)
