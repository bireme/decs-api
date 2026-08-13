# 001 — API endpoint test suite

## Goal

Automated tests that exercise, validate and pin the behaviour of every live endpoint of
the DeCS API, so upgrades like the Django 5.2 / Python 3.14 / Elasticsearch 9 migration
can be verified without manual URL-by-URL comparison against production.

## Status

Specified — not started.

---

## Surface under test

`decs_api/urls.py` routes only `admin/` and `api/`. `api/urls.py` registers a tastypie
`Api(api_name='thesaurus')` with two resources, so the live API surface is:

| URL | Resource | Query modes |
| --- | --- | --- |
| `/api/thesaurus/` | tastypie API index | lists both resources |
| `/api/thesaurus/term/` | `TermResource` | `words`, `bool`, `tree_id` (empty → first level, <3 chars → second level, else tree search) |
| `/api/thesaurus/quickterm/` | `QuickTermResource` | `query` |

Shared parameters: `ths` (default `1`), `status` (default `1`), `lang`
(term default `pt`; quickterm default *no language* → `must_not es-es`), `count`
(quickterm only, default `100`), `format` (`xml` default, `json` opt-in),
`$` accepted as an alias for the `*` wildcard.

**Out of scope:** `app/thesaurus/urls.py` — it is dead code. It imports
`thesaurus.views`, which does not exist, and is not included from `decs_api/urls.py`.
Do not revive it under this feature.

---

## Architecture of the suite

Three layers, in increasing order of infrastructure required.

### Layer 1 — pure unit (no DB, no ES)

`SimpleTestCase`, runs anywhere. Targets `api/esearch_functions.py` and
`api/thesaurus_term_api.get_valid_lang`:

- `f_parse` — the docstring examples, nested groups, `AND NOT` right-associativity,
  Latin-1 terms, terms containing commas/parentheses, and the `ParseException` →
  `Http404` path.
- `get_search_q` — assert the generated Query DSL via `q.to_dict()` for each prefix
  family: `101/102` (preferred vs synonym filter), `103` non-wildcard (match_phrase +
  should boosts), `103` wildcard (word-by-word), `104/107`, `401/402/403` word-by-word,
  multi-word `4##` → `match_none`, `words`, `quick`, `tree_id`, invalid prefix →
  `match_none`. Also the `lang_code is None` → `must_not es-es` branch and the
  `filter_gral` composition for the three `(lang_code, ths)` combinations.
- `truncated_word_must` — mixed wildcard/plain words.
- `get_valid_lang` — `pt`→`['pt','pt-br']`, `en`, `es`, `pt-BR`, unknown → `pt`,
  empty string, and locale forms like `es-AR`.
- `complex_search` — with `execute_simple_search` stubbed, assert the set algebra:
  `AND` intersect, `OR` union preserving first-seen order, `AND NOT` difference,
  `105/106/405/406` expansion into two independent searches, and malformed input
  (bad operator → `[]`).

### Layer 2 — endpoint tests (SQLite test DB, faked ES)

`TestCase` + `django.test.Client`, driving the real URLconf, tastypie resource,
`dehydrate` and serializer. Elasticsearch is replaced at exactly two seams —
`api.thesaurus_term_api.execute_simple_search` and
`api.thesaurus_quickterm_api.execute_quick_search` / `execute_simple_search` — which
return the same list-of-dicts shape the real functions return
(`{'identifier', 'term_type'}` and `{'identifier', 'term_type', 'term_string'}`).
Everything downstream of the search is real code against real rows.

Cases:

**`/api/thesaurus/term/`**
- `words=` → XML root `decsws_response`, `@service`, `@tree_id`, `record/@lang`,
  `@db=decs`, `@mfn`, `descriptor_list` per-language entries, `synonym_list` filtered
  to the requested language, `definition/occ/@n`, `tree_id_list`, `unique_identifier_nlm`.
- `words=` → the echoed `<query>` element carries the original query string.
- `bool=` with a real expression → the resource resolves the parse tree and returns the
  union/intersection of records.
- `tree_id=` (empty) → first-level categories block: `tree/term_list` in the requested
  language, empty `attr.tree_id`.
- `tree_id=C` (<3 chars) → second-level block with `self`, empty `ancestors`,
  `preceding_sibling`, `following_sibling`, populated `descendants`, and the
  `record_list` skeleton (empty `allowable_qualifier_list`, empty definition).
- `tree_id=C01.001` → full record + `tree` with ancestors / self / siblings /
  descendants drawn from `TreeDescriptor`.
- Qualifier records: leading `/` prepended to labels and synonyms, `tree_id_list`
  filtered to the matching `Q`/`Y` prefix, and the four empty descriptor-only lists.
- Descriptor extras: `pharmacological_action_list`, `entry_combination_list` (with the
  `lang` attribute merged into `attr`), `see_related_list`, `allowable_qualifier_list`
  (`@id` = `decs_code`), `indexing_annotation`, `consider_also_terms_at` — each
  language-filtered and `status == 1`-filtered.
- Language handling: `lang=en`, `lang=es`, `lang=pt`, absent (`pt` default),
  unknown (`lang=zz` → falls back to `pt`).
- `format=json` returns `application/json` with the same structure; default (no
  `format`) returns `application/xml`; `Accept: application/json` is honoured by
  `determine_format`.
- Pagination: `NoPaginator` deletes `meta` from term responses (quickterm keeps it).
- No recognised parameter → empty `objects`, HTTP 200.

**`/api/thesaurus/quickterm/`**
- `query=` → `item/@id` (first tree number, ordered by `tree_number`) and `item/@term`;
  qualifier terms prefixed with `/`.
- Top-2 exact block precedes the alphabetical block, and duplicates between the two
  blocks are preserved (old-API behaviour).
- `count=` smaller than the result set truncates; larger leaves the full list.
- `lang=` set vs absent, `ths=`, `status=` are threaded into `get_search_q`
  (asserted via the captured call arguments on the fake).
- `$` → `*` translation, for both `query` and term `words`/`bool`.
- `format=json` and the default XML.
- Missing `query` → empty response, HTTP 200.

**Method and route checks**
- `/api/thesaurus/` index lists `term` and `quickterm`.
- `POST`/`PUT`/`DELETE` on both resources → 405.
- `/api/thesaurus/term/schema/` responds (tastypie built-in).

**Characterization of crash-prone paths** — assert *today's* behaviour, each with a
comment naming the defect and the reproducing request. No behaviour is changed under
this feature; see [Follow-up defects](#follow-up-defects-found-during-specification).

### Layer 3 — live integration (opt-in)

Skipped unless `DECS_TEST_ES=1`. Runs against the real dev MySQL + Elasticsearch
(`make dev_start`, index built) and asserts **pinned values taken from real DeCS
records** — a documented handful of stable descriptors/qualifiers with their real tree
numbers, pt-br/en/es labels and mfn. No network calls to production in this mode.

A second flag, `DECS_TEST_PARITY=1`, additionally diffs each response against
`https://decs-api.bvsalud.org` for the same query — the automated form of plan 003's
manual parity step, for release verification only. Parity comparison normalises
insignificant whitespace and compares parsed structure, and reports the first
differing XPath.

---

## Key decisions

| Branch | Decision |
| --- | --- |
| Scope | `term` + `quickterm` (+ API index, schema, 405s). `thesaurus/urls.py` stays dead. |
| Elasticsearch | Faked at the `execute_*` seam by default; opt-in live layer with real data. |
| Query DSL | Verified separately by asserting `get_search_q(...)['query'].to_dict()`. |
| Test DB | SQLite in-memory via `decs_api/settings_test.py`, with unmanaged models forced to `managed=True` for table creation. |
| Fixtures | JSON fixture files dumped from the dev DB by a new make target. |
| Assertions | Structural — parse XML/JSON and assert elements, attributes, order, counts. |
| Live expectations | Pinned real-record values (`DECS_TEST_ES=1`), plus optional production diff (`DECS_TEST_PARITY=1`). |
| Runner | Django's built-in runner. No new dependencies. |
| Layout | Per-app `tests/` packages. |
| Error paths | Characterized as-is; defects logged as follow-ups, not fixed here. |
| Regressions | Named regression tests for plans 001, 002 and the empty-documents ES bug. |
| CI | Make targets only; no GitHub Actions yet. |

---

## Files

```
app/decs_api/settings_test.py              # new — sqlite, force-managed, deterministic ES config
app/api/tests/__init__.py                  # new
app/api/tests/support.py                   # new — fake ES seam, XML helpers, base cases
app/api/tests/fixtures/decs_sample.json    # new — dumped from dev DB
app/api/tests/test_query_building.py       # new — Layer 1: get_search_q / truncated_word_must
app/api/tests/test_bool_parser.py          # new — Layer 1: f_parse / complex_search
app/api/tests/test_lang.py                 # new — Layer 1: get_valid_lang
app/api/tests/test_term_endpoint.py        # new — Layer 2
app/api/tests/test_quickterm_endpoint.py   # new — Layer 2
app/api/tests/test_routing.py              # new — Layer 2: index, schema, 405s, formats
app/api/tests/test_regressions.py          # new — Layer 2: plans 001 & 002 locks
app/api/tests/test_live.py                 # new — Layer 3, skipped without DECS_TEST_ES
app/thesaurus/tests/__init__.py            # new — package replacing tests.py
app/thesaurus/tests/test_documents.py      # moved from app/thesaurus/tests.py, extended
app/api/thesaurus_term_api.py              # edit — make DECS_LANGUAGES lazy
Makefile                                   # edit — test / dev_test / dev_test_live / dev_dump_test_fixtures
README.md                                  # edit — how to run the three layers
```

---

## Implementation notes

### `settings_test.py`

Imports `*` from `decs_api.settings`, then overrides: SQLite in-memory database, a fixed
`SECRET_KEY` / `ALLOWED_HOSTS` / `DEBUG=0` so the module imports without `conf/app-env`,
`PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']`,
`ELASTICSEARCH_DSL_AUTOSYNC = False` (already the default), and a `LOGGING` config that
silences tastypie's 500 tracebacks for the characterization tests.

### Forcing unmanaged models to be created

The thesaurus models the API reads (`TermListDesc`, `TermListQualif`,
`TreeNumbersListDesc`, `TreeNumbersListQualif`, `PreviousIndexingListDesc`, …) are
`managed = False` in `0001_initial.py`, so `migrate` creates no tables for them. Under
the test settings, connect a `pre_migrate` receiver that flips `managed = True` on every
`thesaurus` and `utils` model before schema creation. Keep this strictly inside
`settings_test.py` / a test-only apps hook so production behaviour is untouched.

Verify early: run `manage.py migrate --settings=decs_api.settings_test` on SQLite and
confirm every table the endpoints touch exists. `jsonfield` 3.2 stores text, so SQLite is
adequate; if any field turns out to be MySQL-only, fall back to running Layer 2 inside
the dev container against MySQL (decision recorded as a fallback, not the default).

### Lazy `DECS_LANGUAGES`

`api/thesaurus_term_api.py:19-20` currently executes a query at import time:

```python
valid_lang = TermListDesc.objects.distinct().values("language_code")
DECS_LANGUAGES = [list(dict_lang.values())[0] for dict_lang in valid_lang]
```

Replace with a cached accessor (module-level `_decs_languages = None`, populated on the
first `get_valid_lang` call, or `functools.cache`). This removes import-time DB access —
which also makes the module import safely before `migrate` at container start — and makes
language tests deterministic instead of dependent on when the URLconf was first loaded.
No API contract change: the resolved language values stay identical. Tests reset/patch the
cache to a known language list. Provide a way to clear the cache so Layer 3 picks up real
data.

### Fake ES seam

`support.py` provides a context manager / mixin that patches
`api.thesaurus_term_api.execute_simple_search`, `api.thesaurus_quickterm_api.execute_quick_search`
and `api.thesaurus_quickterm_api.execute_simple_search` with recording fakes. Each fake
returns a caller-supplied list and stores the `search_q` dict it was handed, so tests can
assert both the rendered response *and* that the right index/query reached ES.

Patch where the name is used, not where it is defined — both API modules do
`from api.esearch_functions import *`, so the names are rebound into each module's
namespace.

### Fixtures

`make dev_dump_test_fixtures` runs `dumpdata` inside the dev container for a documented
record set, written to `app/api/tests/fixtures/decs_sample.json`:

- one descriptor with ≥2 tree numbers, pt-br/en/es labels, synonyms, scope notes,
  annotation, consider-also, pharmacological actions, entry combinations, see-also and
  allowable qualifiers;
- one qualifier with both `Q` and `Y` tree numbers;
- the matching `TreeDescriptor` / `TreeQualifier` rows (ancestors, siblings, descendants);
- `FirstLevel` categories for the first- and second-level `tree_id` branches;
- the `TermListDesc` / `TermListQualif` / `TreeNumbersList*` rows those records need.

The exact record identifiers are written into the make target and echoed in a header
comment in the fixture file, so the dump is reproducible. Fixture size stays reviewable —
a curated slice, never a full dump.

### Regression locks (`test_regressions.py`)

- **Plan 001 — quickterm ordering.** Preferred term first, then case-sensitive byte-order
  alphabetical; assert `execute_quick_search` is called with `top_sorted=True` for
  wildcard queries and that the sort clauses are `record_preferred_term: desc` then
  `term_string.sort: asc`.
- **Plan 002 — wildcard multi-word quickterm.** `query=transtorno espectro au*` routes to
  the word-by-word `103` branch (`truncated_word_must`), not the whole-string
  `full_field` wildcard, so non-contiguous matches survive.
- **Empty-documents ES bug.** Keep the existing `_prepared_fields` guard from
  `thesaurus/tests.py` and extend it to assert `prepare()` returns a non-empty mapping for
  a constructed instance of each registered document.

### Make targets

```make
test:                     # offline layers 1+2, current interpreter
dev_test:                 # same, inside the dev container
dev_test_live:            # DECS_TEST_ES=1, inside the dev container
dev_dump_test_fixtures:   # regenerate app/api/tests/fixtures/decs_sample.json
```

`test` must actually exist — `prod_make_test` already invokes `make test` inside the
container and currently fails.

---

## Acceptance criteria

- `make test` passes with no Elasticsearch, no MySQL and no network.
- Every live endpoint and every documented query mode listed above has at least one test.
- Both response formats (XML default, JSON opt-in) are asserted for each resource.
- The generated Elasticsearch query is asserted for every `get_search_q` branch.
- The three named regressions have dedicated, self-describing tests.
- `make dev_test_live` passes against the dev stack with real data.
- `DECS_TEST_PARITY=1` reports no structural differences against production for the
  documented parity queries.
- No change to API behaviour: the only production edit is the lazy `DECS_LANGUAGES`.
- A log file is written to `.ai/logs/` per `AGENTS.md`.

---

## Follow-up defects found during specification

Recorded, not fixed here — each gets a characterization test pinning current behaviour.

1. **`quickterm` dehydrate can 500.** `thesaurus_quickterm_api.py:150-151` does
   `treeN_list[0].tree_number` with no guard; a term whose identifier has no
   `TreeNumbersList` row raises `IndexError`.
2. **`term` dehydrate can raise `UnboundLocalError`.** `thesaurus_term_api.py:372-384`
   only assigns `full_tree` when a tree id equals the requested `tree_number`; a
   `tree_id` that does not belong to the matched record leaves it unbound.
3. **`term_string` / `term_string_en` may be unbound** in the same function when no label
   matches the requested language or `en` (`thesaurus_term_api.py:270-274`).
4. **Mutation of JSONField payloads during dehydrate.** Qualifier labels and synonyms are
   prefixed in place (`term['@value'] = "/" + …`), mutating the loaded model object —
   harmless today because the object is discarded, fragile if caching is ever added.
5. **`FirstLevel.objects.get(...)` unguarded** at `thesaurus_term_api.py:166` — an unknown
   two-character `tree_id` raises `DoesNotExist` → 500 rather than 404.
6. **Unused imports** in both API modules (`Length`, `Substr`, `settings`,
   `TermListDesc` / `TermListQualif` in the term module) — cosmetic.

---

## Risks

- **SQLite vs MySQL divergence.** Mitigation: the force-managed hook is validated first;
  `make dev_test` runs the same suite in the container if MySQL-specific behaviour surfaces.
- **Fixture drift.** Real-data fixtures go stale when the dev DB is reloaded. Mitigation:
  the dump is a make target with the record ids written down, so it is regenerable.
- **Faked ES hides real query defects.** Mitigation: Layer 1 asserts the exact query DSL,
  and Layer 3 runs the real thing.
- **Tastypie 500-on-exception.** tastypie converts unhandled exceptions into 500 responses
  with `DEBUG=0`; characterization tests must assert the status and the logged exception
  type, not rely on the exception propagating.
