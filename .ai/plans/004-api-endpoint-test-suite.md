# API endpoint test suite

## Context

The DeCS API has no automated tests beyond a single ES-document guard
(`app/thesaurus/tests.py`). Every release so far — the quickterm ordering fix, the
multi-word wildcard fix, the Django 5.2 / Python 3.14 / Elasticsearch 9 upgrade — has been
verified by hand, URL by URL, against production. This feature builds the suite that
replaces that manual pass: three layers covering every live endpoint and query mode, with
named regression locks for the three fixes this branch line shipped.

Spec: [`.ai/features/001-api-endpoint-test-suite.md`](.ai/features/001-api-endpoint-test-suite.md).
No API behaviour changes. The only production edit is making `DECS_LANGUAGES` lazy.

## Decisions taken during planning

Four things the spec left open or got wrong, resolved with the user:

1. **`make test` runs in the dev container.** The host cannot build `mysqlclient` (no Linux
   wheel, `default-libmysqlclient-dev` absent), so a host-side `uv sync` fails.
2. **A custom `TEST_RUNNER` creates the unmanaged tables**, not a `pre_migrate` hook. The
   spec's hook cannot work: with migrations present, table creation follows the migration
   state (`'managed': False` baked into `0001_initial.py`), not the live model `Meta`.
3. **Fixtures are dumped from the dev DB**, per spec — `make dev_dump_test_fixtures`.
4. **All three layers land now**, including the `DECS_TEST_PARITY=1` production diff.

Also found while planning: **neither Docker stage installs `make`**, so the existing
`prod_make_test` (`docker compose exec … make test`) could never have worked even once a
`test` target existed. The container-side targets therefore call `python manage.py test`
directly.

## Which tables actually need help

Verified against `app/thesaurus/migrations/0001_initial.py`: `Descriptor`, `Qualifier`,
`TreeDescriptor`, `TreeQualifier` and `FirstLevel` are **managed** — `migrate` creates them.
Only the list tables are unmanaged: `TermListDesc`, `TermListQualif`, `TreeNumbersListDesc`,
`TreeNumbersListQualif`, `PreviousIndexingListDesc`, `Thesaurus`, and the rest of the
`*ListDesc` / `*ListQualif` family. Of those the API reads `TreeNumbersListDesc`,
`TreeNumbersListQualif` (both `dehydrate`s) and `TermListDesc` (`DECS_LANGUAGES`).

## Implementation

### 1. `app/decs_api/settings_test.py` (new)

`os.environ.setdefault(...)` for `SECRET_KEY` / `DJANGO_ALLOWED_HOSTS` / `DEBUG` **before**
`from decs_api.settings import *` — `settings.py:30` calls `.split(",")` on the env value
and raises without it. Then override: SQLite in-memory, `MD5PasswordHasher`,
`TEST_RUNNER = 'decs_api.test_runner.UnmanagedTablesRunner'`, and a `LOGGING` block
silencing `django.request` so tastypie's 500 tracebacks don't flood the characterization
tests.

### 2. `app/decs_api/test_runner.py` (new)

Subclass `DiscoverRunner`; after `super().setup_databases()`, open
`connection.schema_editor()` and `create_model()` every model in the `thesaurus` and `utils`
app configs whose table is missing from `connection.introspection.table_names()`. Explicit,
order-independent, and immune to migrate internals.

### 3. `app/api/thesaurus_term_api.py` — the one production edit

Replace the import-time query at lines 19–20 with a cached accessor:

```python
@functools.cache
def get_decs_languages():
    return [row["language_code"] for row in TermListDesc.objects.distinct().values("language_code")]
```

`get_valid_lang` (line 428) calls it; tests use `get_decs_languages.cache_clear()`. Same
resolved values, no DB access at import — which also lets the module import before `migrate`
at container start.

### 4. Layer 1 — pure unit (`SimpleTestCase`, no infra)

- `test_query_building.py` — assert `get_search_q(...)['query'].to_dict()` for every branch
  in `app/api/esearch_functions.py:26`: `101/102` (`filter_preferred` vs `filter_synonym`),
  `103` non-wildcard (match_phrase + the two `should` boosts), `103` wildcard
  (`truncated_word_must`), `104/107`, `401/402/403` word-by-word, multi-word `4##` →
  `match_none`, `words`, `quick`, `tree_id`, invalid prefix → `match_none`; plus the
  `lang_code is None` → `must_not es-es` branch and `filter_gral` across the three
  `(lang_code, ths)` combinations. Also `truncated_word_must` with mixed words.
- `test_bool_parser.py` — `f_parse` docstring examples, nested groups, `AND NOT`
  right-associativity, Latin-1 terms, terms with commas/parentheses, `ParseException` →
  `Http404`; `complex_search` with `execute_simple_search` stubbed, asserting AND/OR/AND NOT
  set algebra, `105/106/405/406` expansion, and bad operator → `[]`.
- `test_lang.py` — `get_valid_lang` over `pt`, `en`, `es`, `pt-BR`, `es-AR`, `zz`, `''`,
  against a patched `get_decs_languages` cache.

### 5. Layer 2 — endpoint tests (SQLite, faked ES)

`app/api/tests/support.py` patches `api.thesaurus_term_api.execute_simple_search`,
`api.thesaurus_quickterm_api.execute_quick_search` and
`api.thesaurus_quickterm_api.execute_simple_search` — **where the names are bound**, since
both modules do `from api.esearch_functions import *`. Each fake records the `search_q` it
received and returns a caller-supplied list, so a test asserts both the rendered response
and the query that reached ES. Also XML helpers (`lxml` parse + XPath assertions).

Coverage per the spec's case list: `test_term_endpoint.py` (`words`, `bool`, the three
`tree_id` forms, qualifier `/` prefixing, descriptor extras, languages, both formats,
`NoPaginator` deleting `meta`), `test_quickterm_endpoint.py` (`item/@id` from the first
`tree_number`, top-2-then-alphabetical order with duplicates preserved, `count` truncation,
`$`→`*`, `Result/@count` + `@total` which `QuickDecsSerializer.to_xml:201-209` lifts from
`meta`), `test_routing.py` (API index, `schema/`, 405s, `determine_format` with `Accept`),
and characterization tests for the crash-prone paths, each commented with the defect it
pins.

### 6. Fixtures

`make dev_dump_test_fixtures` runs `dumpdata` in the dev container for a documented record
set → `app/api/tests/fixtures/decs_sample.json`: one rich descriptor (≥2 tree numbers,
pt-br/en/es labels, synonyms, scope notes, annotation, considerAlso, pharmacological
actions, entry combinations, seeAlso, allowable qualifiers), one qualifier with both `Q` and
`Y` tree numbers, the matching `TreeDescriptor` / `TreeQualifier` rows, `FirstLevel`
categories, and the `TermList*` / `TreeNumbersList*` rows those need. Record ids are written
into the make target and echoed in a header comment so the dump is reproducible.

*Blocking dependency:* this needs the dev stack up and populated. If the dev DB turns out to
be empty, this step stops and I check in rather than silently switching to hand-built
factories.

### 7. Layer 3 — live (`test_live.py`)

Skipped unless `DECS_TEST_ES=1`; real MySQL + ES, pinned values from a documented handful of
stable DeCS records. `DECS_TEST_PARITY=1` additionally fetches the same query from
`https://decs-api.bvsalud.org`, normalises insignificant whitespace, compares parsed
structure and reports the first differing XPath.

### 8. Regression locks (`test_regressions.py`)

- **Plan 001** — quickterm ordering: `execute_quick_search` called with `top_sorted=True`
  for wildcard queries, sort clauses `record_preferred_term: desc` then `term_string.sort: asc`.
- **Plan 002** — `query=transtorno espectro au*` routes to the word-by-word `103` branch,
  not the whole-string `full_field` wildcard.
- **Empty documents** — keep the `_prepared_fields` guard from `app/thesaurus/tests.py`
  (moved to `app/thesaurus/tests/test_documents.py`) and extend it to assert `prepare()`
  returns a non-empty mapping per registered document.

### 9. Makefile + README

```make
test:                     # docker compose exec -T decs_api_app python manage.py test --settings=decs_api.settings_test
test_live:                # same, with DECS_TEST_ES=1
dev_dump_test_fixtures:   # regenerate app/api/tests/fixtures/decs_sample.json
```

`prod_make_test` is repointed at `python manage.py test --settings=decs_api.settings_test`
inside the prod container — it currently calls a `make` binary that no image contains.
README gains a section on the three layers and the two env flags.

## Follow-up defects (characterized, not fixed)

The six from the spec, plus one found while planning: `QuickTermResource.get_search`
(`app/api/thesaurus_quickterm_api.py:128-131`) assigns `self._meta.limit`, mutating
resource-level state across requests — tests must not depend on request ordering.

## Verification

1. `make dev_start && make dev_dump_test_fixtures` — fixtures regenerate from real data.
2. `make test` — layers 1+2 green in the container, with ES unreachable and MySQL untouched
   (SQLite in-memory).
3. Confirm the runner really created the unmanaged tables: a test asserting
   `TreeNumbersListDesc.objects.count()` matches the fixture.
4. `make test_live` with the index built (`make dev_search_index_build`) — layer 3 green.
5. `DECS_TEST_PARITY=1 make test_live` — no structural differences against production.
6. Spot-check no behaviour change: `curl` a `words=`, a `tree_id=` and a `query=` request
   against the dev container before and after the `DECS_LANGUAGES` edit; responses identical.
7. Write `.ai/logs/2026-08-12-api-endpoint-test-suite.md` per `AGENTS.md`.
