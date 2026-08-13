# 2026-08-12 — API endpoint test suite

Plan: [`.ai/plans/004-api-endpoint-test-suite.md`](../plans/004-api-endpoint-test-suite.md)
Spec: [`.ai/features/001-api-endpoint-test-suite.md`](../features/001-api-endpoint-test-suite.md)

Automated tests for every live endpoint and query mode of the DeCS API, so releases can be
verified without the manual URL-by-URL comparison against production that plans 001–003
relied on.

## What was added

| File | Purpose |
| --- | --- |
| `app/decs_api/settings_test.py` | SQLite in-memory, env defaults, fixture dir, quiet logging |
| `app/decs_api/test_runner.py` | creates the tables the unmanaged models need |
| `app/api/tests/support.py` | fake Elasticsearch seam, fixture constants, XML/JSON helpers |
| `app/api/tests/test_query_building.py` | layer 1 — every `get_search_q` branch |
| `app/api/tests/test_bool_parser.py` | layer 1 — `f_parse` and `complex_search` |
| `app/api/tests/test_lang.py` | layer 1 — `get_valid_lang` and the language cache |
| `app/api/tests/test_term_endpoint.py` | layer 2 — `/term/` in all its modes |
| `app/api/tests/test_quickterm_endpoint.py` | layer 2 — `/quickterm/` |
| `app/api/tests/test_routing.py` | layer 2 — index, schema, 405s, format negotiation |
| `app/api/tests/test_regressions.py` | named locks for plans 001, 002 and the empty-document bug |
| `app/api/tests/test_live.py` | layer 3 — live stack, plus the production parity diff |
| `app/api/tests/fixtures/decs_sample.json` | 101 objects dumped from the dev database |
| `app/thesaurus/tests/test_documents.py` | moved from `tests.py`, extended with a real `prepare()` |
| `scripts/dump_test_fixtures.py` | regenerates the fixture; documents the record set |
| `scripts/wait_for_api.py` | waits for the server `make dev_test_live` starts |

160 tests. `make dev_test` runs 148 of them with no Elasticsearch, no MySQL and no network; the
12 live ones skip unless `DECS_TEST_ES=1`.

## Production change

One, as planned: `api/thesaurus_term_api.py` no longer queries the database at import time.
`DECS_LANGUAGES` became `get_decs_languages()`, a `functools.cache`d accessor called from
`get_valid_lang`. Same resolved values; the module now imports before `migrate`, and the
language list no longer depends on when the URLconf was first loaded.

`Makefile` gained `dev_test`, `dev_test_live`, `dev_test_parity` and `dev_dump_test_fixtures`, and
the old `prod_make_test` became `prod_test` and was repointed: it ran
`docker compose exec … make test`, but no Docker stage installs `make`, so it could never
have worked.

## Things the plan had wrong

**The `pre_migrate` hook could not have worked.** With migrations present, table creation
follows the migration state — `'managed': False` is recorded in `0001_initial.py` — not the
live model `Meta`, so flipping `managed` at runtime changes nothing.
`decs_api/test_runner.py` creates the tables explicitly instead, after `setup_databases()`.

Two details only visible once it ran:

- `create_model()` also creates m2m through tables, so concrete models are created first and
  the table list is re-read every iteration.
- The DeCS database holds NULL in many columns the models declare NOT NULL (`blank=True`
  without `null=True`). The test tables are built with every non-key column nullable, so the
  fixtures load as dumped rather than being edited to fit.

**Fewer tables were missing than the spec assumed.** `Descriptor`, `Qualifier`,
`TreeDescriptor`, `TreeQualifier` and `FirstLevel` are managed and created by `migrate`.
Only the `*List*` family is unmanaged.

## Things found while writing the tests

1. **`bool=` bypassed the fake seam.** `complex_search()` resolves `execute_simple_search`
   in its own module, so patching the two API modules is not enough — an early version of
   the suite silently queried the real cluster. `support.py` patches
   `api.esearch_functions.execute_simple_search` as well.
2. **`/schema/` is broken on both resources** (new; not in the spec's list). tastypie's
   `build_schema()` calls `get_object_list(request)`, while both resources declare
   `get_object_list(self, bundle)` and read `bundle.request` →
   `AttributeError: 'WSGIRequest' object has no attribute 'request'` → HTTP 500.
   Characterized in `test_routing.py`.
3. **`QuickTermResource` leaks its page size between requests** — `self._meta.limit` is
   resource-level state (`thesaurus_quickterm_api.py:128-131`). A request with no `query`
   reports the previous request's count. Characterized.
4. **An unsupported `format=` is not rejected**, it falls back to XML.
5. **`Generic.__init__` recurses forever on a deferred queryset.** It builds a
   `model_to_dict()` of every field, so a row loaded with `.only("pk")` reloads itself on
   each deferred access, constructing another instance each time — Django's serializer does
   exactly that for m2m fields. The dump script skips `IdentifierDesc.abbreviation`, which
   no endpoint reads.
6. **Spec defect 3 is not observable.** `term_string` / `term_string_en` can indeed be left
   unbound in `thesaurus_term_api.py:270-274`, but nothing reads them in that branch, so
   there is no behaviour to characterize.

Defects 1, 2 and 5 from the spec (`treeN_list[0]`, unbound `full_tree`, unguarded
`FirstLevel.objects.get`) each have a characterization test asserting today's 500. Defect 4
(in-place mutation of the JSONField payload) has a test proving the `/` prefix is not
applied twice across requests — the assertion that would fail if records were ever cached.

## Verification

- `make dev_test` — 160 tests, 12 skipped, green.
- `make dev_dump_test_fixtures` — regenerates the fixture from the dev database.
- `make dev_test_live` — **8 of 12 fail, for an environmental reason.** The Elasticsearch at
  `172.17.1.93` still holds the empty documents from the pre-`b6a6a7a` indexing bug
  (`_source: {}` on every hit, `descriptor_term` at ~15 bytes per document), so every
  search returns nothing. The four tests that do not depend on the index pass. The live
  layer needs `make dev_search_index_build` against that cluster before it can be trusted;
  until then `make dev_test_parity` is untested too.
