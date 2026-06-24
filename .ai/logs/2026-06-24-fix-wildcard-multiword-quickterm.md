## Changes made — multi-word wildcard (`*`) in quickterm

### 1. `truncated_word_must(text)` helper (`esearch_functions.py`)
Builds word-by-word AND clauses for truncated queries: each word is a `must` on
the analyzed `term_string`; words with `*` use `wildcard`, others use `match`.
Reproduces the old API "palabra a palabra" semantics and matches non-contiguous
queries (e.g. `transtorno espectro au*` → "Transtorno **do** Espectro Autista").

### 2. `'quick'` branch (alphabetical phase)
Replaced `Q('wildcard', term_string=text)` (failed on multi-word) with
`truncated_word_must(text)` for truncated queries.

### 3. `'103'` branch (top-2 phase)
- `thesaurus_quickterm_api.py`: pass the wildcard-bearing `query` (not stripped
  `query0`) to `get_search_q('103', …)`.
- `esearch_functions.py`: new explicit `elif op_prefix == '103':` using
  `truncated_word_must` (does not fall through to the `1##` full_field wildcard,
  which is whole-string only and would miss non-contiguous matches).

### 4. Deterministic wildcard top-2 (`execute_quick_search`)
Added `top_sorted` param; when set (wildcard queries), sort the size-2 phase by
`record_preferred_term:desc, term_string.sort:asc` (preferred first, then byte
order) to match the old API. Non-wildcard top-2 relevance scoring untouched.

### 5. Docs
`docs/quickterm-search-issues.md`: issue #1 marked resolved.

### Verification (local dev server vs old API)
- `doenca de cha*` → PASS (4 items, exact)
- `transtorno espectro au*` → PASS (5 items, exact)
- `sindrome respi*` → set identical (83); only top-2 relevance order differs
- `insuficiencia cardiaca` → PASS (no regression)
- `dengue` → differs by French terms only (data drift)

No reindex needed (existing fields only).

## What changed

| File                                           | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `app/api/esearch_functions.py`                 | **(A)** New `truncated_word_must()` helper — builds word-by-word AND clauses (wildcard on the `*` word, `match` on the rest). Used in the `'quick'` branch. **(B)** New explicit `elif op_prefix == '103':` branch using the same helper, so the top-2 phase doesn't fall through to the contiguous `1##` full_field wildcard. **(C)** `execute_quick_search(..., top_sorted=...)` sorts the wildcard top-2 by `record_preferred_term desc, term_string.sort asc`. |
| `app/api/thesaurus_quickterm_api.py`           | **(B)** Passes the wildcard-bearing `query` (not stripped `query0`) to `'103'`, and enables `top_sorted` for wildcard queries.                                                                                                                                                                                                                                                                                                                                     |
| `docs/quickterm-search-issues.md`              | **(D)** Issue #1 marked resolved.                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `.ai/plans/002-…md`, `.ai/logs/2026-06-24-…md` | Plan + log, matching the existing convention.                                                                                                                                                                                                                                                                                                                                                                                                                      |

## Root cause
The old API matches **word-by-word (AND)** with the truncated word as a prefix — not a contiguous phrase. The old code used `Q('wildcard', term_string=text)` on the *analyzed* field, which can't match a multi-word pattern against single tokens (returned 0), and the top-2 phase stripped the `*` and required an exact token. My first attempt (`full_field` wildcard) was contiguous and broke `transtorno espectro au*` (skips the intervening "do") — the word-by-word approach handles that correctly.

## Validation (local dev server vs old API)
- ✅ `doenca de cha*` — **4 items, exact match** (was 0)
- ✅ `transtorno espectro au*` — **5 items, exact match** (was 0; non-contiguous)
- ✅ `insuficiencia cardiaca` — **16 items, exact** (non-wildcard, no regression)
- ⚠️ `sindrome respi*` — was 0, **now returns the correct 83-item set with correct alphabetical body**; the only diff is the top-2 "most relevant" pair, where the old API's opaque relevance picks the *Desconforto Respiratório* descriptor (same nuance already documented for non-wildcard `sindrome respiratoria`).
- ⚠️ `dengue` — fails only on French terms (data drift), pre-existing and unrelated to this change.

**No reindex required** — uses existing fields. The two remaining FAILs are the previously-established top-2-relevance and data-drift caveats, not regressions from this fix.

One note: I validated against your local dev container using a `Host: decs-api.local` header (its `ALLOWED_HOSTS`), via a scratchpad runner — `scripts/diff_quickterm.py` itself defaults to the teste env and doesn't send that header, so it can't hit localhost as-is. Want me to add an optional `--host-header`/local flag to the committed script so you can point it at the dev server directly?
