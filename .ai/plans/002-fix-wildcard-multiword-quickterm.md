# Fix multi-word wildcard (`*`) in `/api/thesaurus/quickterm/`

## Context

Truncated searches with `*` returned **0 results** whenever the query had more
than one word (docs issue #1), e.g. `doenca de cha*`, `transtorno espectro au*`,
`sindrome respi*`. The old `decsQuickTerm` API returns hits for all of these.

### Root cause

Both search phases missed for multi-word wildcards:

1. **Alphabetical phase (`'quick'`, `esearch_functions.py`)** used
   `Q('wildcard', term_string=text)`. A `wildcard` query is *not analyzed* and
   matches against a *single indexed token*, but `term_string` is an analyzed
   `TextField` (tokenized into individual words). There is no single token
   `"doenca de cha*"`, so multi-word wildcards matched nothing. (Single-word
   `cha*` worked because it can match one token.)

2. **Top-2 phase (`'103'`, `thesaurus_quickterm_api.py`)** received `query0`
   (the query with `*` stripped) and hit the `match_phrase` branch, which
   requires the exact token `cha` — but the term has `chagas` — so it returned 0.

### Old-API semantics (observed)

The old API matches **word by word (AND)**, not as a contiguous phrase, with the
truncated word as a prefix:

- `transtorno espectro au*` → `Transtorno do Espectro Autista`,
  `Transtorno de Espectro Autista`, `Transtorno do Espectro do Autismo`
  (the intervening `do`/`de` is skipped — a contiguous/full_field wildcard
  cannot do this).
- Top-2 "most relevant" pair is ordered **preferred term first, then
  alphabetically** (byte order): `doenca de cha*` → `Chagas`, `Charcot`
  (both preferred → alphabetical); `transtorno espectro au*` →
  `…do Espectro Autista` (preferred) before `…de Espectro Autista` (synonym).

## Changes (A–D)

### A. `'quick'` branch — word-by-word truncated query
`esearch_functions.py`: when `*` is present, build clauses with the new
`truncated_word_must(text)` helper — each word is a `must` AND on `term_string`;
the word(s) containing `*` use `wildcard`, the rest use `match`. Single-word
wildcard behavior is unchanged (one clause).

### B. `'103'` top-2 — pass the wildcard query + dedicated branch
- `thesaurus_quickterm_api.py`: call `get_search_q('103', query, …)` with the
  wildcard-bearing `query` instead of the stripped `query0`. For non-wildcard
  queries `query == query0`, so nothing changes there.
- `esearch_functions.py`: add an explicit `elif op_prefix == '103':` branch that
  reuses `truncated_word_must`. This deliberately does **not** fall through to
  the generic `1##` full_field wildcard (which is whole-string "campo entero"
  semantics for the bool-expression API and must stay contiguous).

### C. Deterministic top-2 order for wildcards
`esearch_functions.py` `execute_quick_search(..., top_sorted=False)`: when
`top_sorted` is set (wildcard queries only), sort the size-2 phase by
`record_preferred_term:desc` then `term_string.sort:asc` (preferred first, then
byte-order alphabetical) so the top-2 deterministically match the old API.
Non-wildcard top-2 keeps its `match_phrase` relevance scoring untouched.

### D. Docs
`docs/quickterm-search-issues.md`: mark issue #1 resolved.

## Verification

Diff old API vs the local dev server (Host: `decs-api.local`):

| query | result |
|-------|--------|
| `doenca de cha*` | **PASS** — 4 items, exact order |
| `transtorno espectro au*` | **PASS** — 5 items, exact order |
| `sindrome respi*` | set identical (83=83); only the top-2 "most relevant" pair differs (old API's opaque relevance picks the *Desconforto Respiratório* descriptor) — same nuance as non-wildcard `sindrome respiratoria` |
| `insuficiencia cardiaca` | **PASS** — 16 items (non-wildcard, no regression) |
| `dengue` | set differs by French terms only (data drift, pre-existing) |

No reindex required — uses existing fields (`term_string`, `term_string.sort`,
`record_preferred_term`).

## Out of scope / known limitations
- The `'words'` branch (`/words` endpoint) has the identical
  `Q('wildcard', term_string=text)` bug; not changed here.
- Wildcard patterns are not analyzed, so the truncated word is
  case/diacritic-sensitive (must be typed ASCII/lowercase, e.g. `au*`). The
  non-wildcard words still go through the analyzer. Consistent with prior
  single-word wildcard behavior.
- The top-2 "most relevant" order for high-frequency wildcard queries
  (`sindrome respi*`) still depends on the old API's opaque relevance ranking;
  the result *set* and alphabetical body match exactly.
