# Parity check script — test vs production, JSON and XML

## Context

The suite added in `98fef12` has three layers. Layers 1 and 2 (`app/api/tests/`) are
hermetic and belong to the app. Layer 3 (`app/api/tests/test_live.py`) drives the API over
HTTP, and under `DECS_TEST_PARITY=1` it *also* diffs each response against production.

That parity mode has three problems:

1. It lives inside the Django test suite, so it needs a container, `manage.py`,
   `settings_test`, a database and a running server just to compare two remote URLs.
2. It only compares **XML**. `format=json` is a supported, separately-serialized code path
   (`WsDecsSerializer` / `QuickDecsSerializer` build XML by hand; JSON is plain tastypie
   output of a different dict shape) and is never compared.
3. It only covers the seven queries the live tests happen to make, and only as a side
   effect of asserting pinned values.

The outcome wanted: a standalone script under `scripts/`, runnable against any two
deployments with nothing but Python, that fetches a fixed matrix of requests from both in
both formats and reports whether the responses are equal.

## Approach

One new file, `scripts/parity_check.py`, self-contained (stdlib + `lxml`, exactly what
`test_live.py` already uses — no `requests`, which is not a declared dependency). It
follows the shape of the existing `scripts/diff_quickterm.py`: argparse, a query matrix,
per-case console report, exit code.

### Comparators

Lift `normalize()` and `first_difference()` from `app/api/tests/test_live.py:50-83`
verbatim into the script — they already walk two lxml trees and return the first differing
path, ignoring `VOLATILE_ATTRIBUTES = {'date'}` (the `date` stamp on `<decsvmx>`, set in
`ws_decs_serializer.py:48`). Add a JSON sibling:

- `first_difference_json(left, right, path='$')` — recursive over dict / list / scalar,
  returning a JSONPath-ish string for the first divergence (`$.objects[0].decsws_response
  .record_list.record.attr.mfn (…)`). Report differing key sets, differing list lengths,
  and differing scalars. There is no volatile field in JSON — term drops `meta` entirely
  (`NoPaginator.page()` at `thesaurus_term_api.py:47`) and quickterm's `meta` holds only
  `limit` / `offset` / `total_count`, all of which *should* match.

### Request matrix

A module-level `CASES` list of `(name, path, params)`, each fetched twice per environment
(`format=xml`, `format=json`). Seed it from what the live tests already exercise, plus the
parameter combinations layer 2 covers that never reach a real deployment:

- `/api/thesaurus/` — the index (both formats).
- `/api/thesaurus/term/` — `words=Músculos`; `words=Muscles&lang=en`; `words=muscul$`
  (wildcard alias); `words=Serotonina&lang=es`; `bool=101 Músculos`;
  `bool=101 Músculos OR 101 Serotonina`; `bool=101 Músculos AND 101 Serotonina`;
  `tree_id=` (first level); `tree_id=A` (second level); `tree_id=A02.633`;
  `tree_id=Q45.020.010` (qualifier); `ths=2`; `status=0`; `lang=zz` (fallback).
- `/api/thesaurus/quickterm/` — `query=Músculos`; `query=mus&count=5`; `query=muscul*`;
  `query=sindrome pe*`; `query=transtorno espectro au*` (the plan-002 regression);
  `query=insuficiencia cardiaca`; `query=covid`; `query=musculos&lang=en`; `count=1`.

Pinned values stay out of this script — it asserts *equality between two deployments*,
nothing about content. That is layer 3's job and it keeps working.

### Environments

Defaults unchanged from what the repo already uses, both overridable:

- `--base-a`, default `$DECS_TEST_URL` or `http://localhost:8000`
- `--base-b`, default `$DECS_TEST_PARITY_URL` or `https://decs-api.bvsalud.org`

Point A at `https://decs-api.teste.bvsalud.org` for the teste-vs-production run. Reuse the
`User-Agent` override from `test_live.py:33` — the production proxy rejects
`Python-urllib/x.y`. No auth: both resources are anonymous GET (`is_authenticated` is
commented out at `thesaurus_term_api.py:95`).

### Strictness

Strict by default: any structural difference fails. Relaxing flags:

- `--ignore-order` — compare `<record>` / `<item>` children as multisets keyed by
  `@mfn` / `@id`, reporting missing / extra / changed instead of positional diffs. Same
  for the JSON `objects` list.
- `--ignore-count` — tolerate differing result counts, comparing only the intersection;
  implies the keyed comparison above.
- `--relaxed` — both of the above, for when the two indexes are known to differ.
- `--ignore-attr NAME` (repeatable) — extend `VOLATILE_ATTRIBUTES`.

Other flags: `--case NAME` / `--path PREFIX` to run a subset, `--format {xml,json,both}`
(default `both`), `--timeout`, `-v` for full unified diffs rather than the first
difference only.

### Output

Per case, one line per format: `PASS`/`FAIL`/`ERROR` with the first differing path. On
failure, a `difflib.unified_diff` of the two pretty-printed payloads
(`etree.tostring(pretty_print=True)` / `json.dumps(sort_keys=True, indent=2)`), truncated
unless `-v`. A summary table at the end; `sys.exit(1)` if anything failed or errored, `0`
otherwise — same contract as `diff_quickterm.py:144`.

### Wiring

- `Makefile`: replace `dev_test_parity` (currently `$(MAKE) dev_test_live
  DECS_TEST_PARITY=1`) with a target that runs the script directly. It needs no container,
  but `lxml` lives in the container venv, so run it the same way as
  `dev_dump_test_fixtures` — `docker compose run --rm --no-deps -T -v $(CURDIR)/scripts:
  /scripts decs_api_app python /scripts/parity_check.py $(PARITY_ARGS)`.
- `app/api/tests/test_live.py`: drop `PARITY`, `PRODUCTION_URL`, `VOLATILE_ATTRIBUTES`,
  `normalize`, `first_difference`, `assertMatchesProduction` and the `if PARITY:` branch in
  `LiveTestCase.get()`. This is the point of the exercise — parity leaves the app tests.
  The live assertions themselves are untouched.
- `Makefile`: `dev_test_live` loses its `-e DECS_TEST_PARITY=$(DECS_TEST_PARITY)`.
- `README.md` lines 15-44: update the table and the env-var paragraph — `make
  dev_test_parity` is now a standalone script, and `DECS_TEST_PARITY` no longer exists.
- `.ai/logs/2026-08-17-parity-check-script.md` per `AGENTS.md`.

## Files

| File | Change |
| --- | --- |
| `scripts/parity_check.py` | new — the whole script |
| `app/api/tests/test_live.py` | remove the parity branch and its helpers |
| `Makefile` | rewrite `dev_test_parity`, trim `dev_test_live` |
| `README.md` | tests section |
| `.ai/logs/2026-08-17-parity-check-script.md` | new |

## Verification

1. `make dev_test` — layers 1+2 still green (148 tests, no infra).
2. `make dev_test_live` — layer 3 still green with the parity branch gone.
3. Self-comparison, must be all PASS: run the script with both bases pointing at
   production. This proves the comparator does not report false differences (in
   particular that `date` is correctly ignored and result ordering is stable).
4. Negative control: point `--base-b` at the legacy quickterm service or pass
   `--ignore-attr` nothing while comparing a deliberately mismatched case, and confirm a
   `FAIL` with a sensible path and exit code 1.
5. The real run: `--base-a https://decs-api.teste.bvsalud.org` against the production
   default, XML and JSON, strict; then again with `--relaxed` to separate genuine
   structural differences from index-content differences.
