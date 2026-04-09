# Match `/api/thesaurus/quickterm/` ordering to the old DeCS API

## Context

The old `decsQuickTerm` API at `srv.bvsalud.org/decsQuickTerm/search` and the
new `/api/thesaurus/quickterm/` endpoint return the *same set* of terms for
`query=sindrome%20respiratoria` (35 items), but the **order differs** and a
docs note (`docs/quickterm-search-issues.md`) flags that the first descriptors
returned by the new API are not the most relevant. Goal: make the new API
reproduce the old API's ordering so downstream consumers (Pesquisa, iAHx,
legacy integrations) can cut over without regressions.

### Observed differences (query=sindrome respiratoria)

Old API top items:
1. `C01.748.730` Síndrome Respiratória Aguda Grave
2. `C01.748.730` Síndrome Respiratória Aguda Severa
3. `...937.500` Coronavírus 2 Causador de Síndrome Respiratória Aguda Grave
…
13. `C01.748.730` Síndrome Respiratória Aguda Grave  ← **repeated**
14. `C01.748.730` Síndrome Respiratória Aguda Severa ← **repeated**

New API top items:
1. `...937.500` Coronavírus 2 Causador de Síndrome Respiratória Aguda Grave
…
19. `C01.748.730` Síndrome Respiratória Aguda Grave (only once)

Three concrete divergences:

1. **Exact / "top 2 most relevant" phase is silently returning 0 hits.**
   `app/api/thesaurus_quickterm_api.py:114` calls `get_search_q('103', …)`
   which in `esearch_functions.py:137-148` builds
   `Q('match', term_string__full_field=text)` with `size=2`. For
   `sindrome respiratoria` this yields nothing (likely because
   `term_string.full_field` is mapped as a non-analyzed/keyword-ish field and
   a `match` on a multi-word phrase never hits a full-field value). Old API
   surfaces "Síndrome Respiratória Aguda Grave / Severa" at positions 1–2,
   so its "top" query is a **relevance-scored phrase/prefix match against
   the full term string**, not a literal equality.

2. **Alphabetical sort is case-insensitive in the new API, case-sensitive
   (ASCII/byte order) in the old API.** Evidence — old order within the
   Coronavírus block puts `Relacionada/Relacionado` before `da` because
   uppercase `R`(82) < lowercase `d`(100); the new API, sorting on
   `term_string.raw` with a lowercase normalizer, puts `da` first. Same
   pattern in the Suína block (`Reprodutiva` before `da Infertilidade` /
   `do Aborto` in the old API, reversed in the new). Matching the old
   ordering requires a **case-sensitive/byte-order sort key**.

3. **The new API deduplicates the alphabetical results against the top-2
   exact results** (`thesaurus_quickterm_api.py:120-122`). The old API does
   **not** dedupe — the top descriptors appear at both position 1–2 and
   again at their alphabetical position (13–14 in the sample). To match,
   drop the dedup step (or at least don't dedupe the exact-match prefix
   against the alphabetical list).

## Critical files

- `app/api/thesaurus_quickterm_api.py` — `QuickTermResource.get_search`,
  lines 102–128: orchestrates the two-phase search and the dedup merge.
- `app/api/esearch_functions.py`
  - `get_search_q` op_prefix `'103'` (lines 137–148): the "top 2" query —
    needs to become a relevance-scored phrase query on the analyzed
    `term_string` field.
  - `get_search_q` op_prefix `'quick'` (lines 82–103): alphabetical query;
    sort key lives in `execute_quick_search`.
  - `execute_quick_search` (lines 208–246): `size=2` branch for exact,
    `sort({'term_string.raw':'asc'})` branch for alphabetical — the sort
    field is the lever for case-sensitive ordering.
- `docs/quickterm-search-issues.md` — original bug report; update once the
  fix lands.

## Planned changes

### 1. Fix the "top 2 most relevant" phase

In `esearch_functions.py` `get_search_q('103', …)` (lines 137–148), replace
the current `match` on `term_string__full_field` with a relevance-scored
query against the analyzed `term_string` field that rewards terms where the
query phrase appears close to the start. Concretely, build a `bool` query
whose `must` is `match_phrase` on `term_string` with a small `slop`, and
whose `should` clauses boost:

- `match_phrase_prefix` on `term_string` (prefix match → short descriptors
  like "Síndrome Respiratória Aguda Grave" float up),
- exact-token `term` match on `term_string.raw` (perfect hit wins).

Keep the `must_not: language_code=es-es` / `filter_gral` the same so the
thesaurus/status/language filters are unchanged. `execute_quick_search`
continues to take the top 2 by ES `_score`.

If `term_string` is not an analyzed text field in the current mapping,
confirm the mapping in `app/thesaurus/documents.py` (or wherever the ES
`DocType` is declared) first and, if needed, use
`term_string.full_field` only as a boosting `should` rather than the sole
`must`.

### 2. Make the alphabetical sort case-sensitive (byte order)

In `execute_quick_search` (`esearch_functions.py:222`), change the sort so
it orders by a keyword field without the lowercase normalizer. Options,
preferred first:

- If the mapping already exposes a raw keyword subfield without normalizer,
  sort on it directly (e.g. `term_string.keyword` or a new
  `term_string.sort`).
- Otherwise add a `sort`-only subfield on `term_string` in the index
  mapping (`keyword`, no normalizer) and reindex. This is the cleanest fix
  and keeps the existing `.raw` field for any case-insensitive consumers.

Document the chosen field in `esearch_functions.py` alongside the sort
call.

### 3. Stop deduplicating the top-2 exact hits out of the alphabetical list

In `thesaurus_quickterm_api.py:120-122`, change the merge so the
alphabetical list is appended **in full** after the top-2 block, preserving
the duplicates the old API emits. The dedup inside
`execute_quick_search` (lines 243–244) can stay — it only suppresses
duplicates *within* the alphabetical phase, which matches old behavior.

Update the `count`/`limit` calculation (lines 124–127) accordingly, since
`len(items)` will now be slightly larger.

### 4. Clean up the docs note

Once the fix is verified, update `docs/quickterm-search-issues.md`: mark
issue #2 (relevance ordering) as resolved and reference the commit. Leave
issue #1 (wildcard + multi-word, e.g. `sindrome respi*`) as out of scope
for this change — it's a separate wildcard-query bug in the `'quick'`
branch at `esearch_functions.py:88-92`.

## Verification

1. **Spin up the local stack** (Django + ES) per project README.
2. **Diff the two APIs** for a fixed set of queries. Create a small
   one-shot script (not committed) that hits both:
   - `sindrome respiratoria` (the canonical regression case)
   - `coronavirus` (single word, many hits)
   - `dengue` (short, high-frequency term)
   - `insuficiencia cardiaca` (multi-word, common)
   - `covid` (acronym)
   For each query, parse the XML from both endpoints and assert that the
   ordered list of `(tree_number, term)` pairs from the new API matches
   the old API exactly (allow the known es-es exclusions if they differ).
3. **Unit test**: add a regression test under `app/api/tests/` that mocks
   `execute_quick_search` (or uses a fixture ES index if one exists) and
   asserts the merge logic in `QuickTermResource.get_search` preserves
   top-2 ordering *and* keeps the duplicates.
4. **Manual spot check in the browser** against the teste environment
   after deploy:
   - `https://decs-api.teste.bvsalud.org/api/thesaurus/quickterm/?query=sindrome%20respiratoria`
     should match `https://srv.bvsalud.org/decsQuickTerm/search?query=sindrome%20respiratoria`
     item-for-item in order.
5. **Performance check**: the alphabetical phase still caps at `size=1000`;
   confirm p95 latency on the diff script doesn't regress vs. baseline.
