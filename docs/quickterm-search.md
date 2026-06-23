# Quick Term Search (Elasticsearch)

## Overview
The quick term endpoint (`/api/thesaurus/quickterm/`) returns preferred terms and synonyms from DeCS/MeSH using Elasticsearch. It combines a small "exact" result set with a broader, alphabetically sorted set and outputs a compact XML or JSON payload.

Key modules:
- `app/api/thesaurus_quickterm_api.py` — resource, request parsing, result assembly.
- `app/api/esearch_functions.py` — Elasticsearch DSL query builders and executors.
- `app/api/ws_decs_serializer.py` — XML shaping for quick search responses.

## Request Parameters
- `query` (required): search text. `$` is converted to `*`. `*` enables wildcard.
- `lang` (optional): language code (validated via `get_valid_lang`). When omitted, results exclude Spanish `es-es` via `must_not`.
- `ths` (default `1`): thesaurus id.
- `status` (default `1`): term status filter.
- `count` (default `100`): max items returned.

Example:
- `GET /api/thesaurus/quickterm/?query=acute%20abdom*&lang=en&count=25`

## Indices and Fields
Search runs against:
- `descriptor_term` and `qualifier_term` indices.
Important fields used:
- `term_string` (text/keyword, supports `.raw`).
- `term_string__full_field` (exact/full-field matching).
- `language_code`, `status`, `term_thesaurus` for filtering.

## Query Construction
Implemented in `get_search_q(op_prefix='quick', ...)`:
- Word-level match with AND semantics: `Q('match', term_string={"query": text, "operator": "AND"})`.
- Wildcard: `Q('wildcard', term_string=text)` when `*` present.
- Filters: `status`, optional `language_code`, and `term_thesaurus` are applied via `filter`.
- When `lang` is omitted, a `must_not Q('match', language_code="es-es")` excludes Spanish.

QuickTermResource executes two searches and merges unique items:
1) Exact top hits (size 2) using prefix `103` (full-field):
   - `match` or `wildcard` on `term_string__full_field`.
   - Size limited to 2 to privilege exact descriptor/qualifier.
2) Alphabetical quick search of broader matches:
   - Same base query as `quick`, sorted by `term_string.raw` ascending.
   - Size up to 1000; then trimmed with `count`.

Query execution (`execute_quick_search`):
- Exact: `Search(...).query(q).extra(size=2)`.
- Sorted: `Search(...).query(q).sort({'term_string.raw':'asc'}).extra(size=1000)`, with `count()` then slice to full range for correct totals.

## Result Assembly
Each hit maps to `{ identifier, term_type, term_string }` where `term_type ∈ {descriptor, qualifier}` and `identifier` is the concept's identifier.
- Duplicates are removed while preserving order (exact hits first, then alphabetical).
- Paginator limit is set to `min(count, len(items))`.

Serialization (`dehydrate` + `QuickDecsSerializer`):
- For descriptors: `term` is the label; for qualifiers: prefixed with `/`.
- First tree number is resolved from relational tables to populate `id`:
  - Descriptors: `TreeNumbersListDesc`.
  - Qualifiers: `TreeNumbersListQualif`.
- XML root: `<DeCSTermService version="1.0">` with `<Result count=".." total="..">` and child `<item id="TREE" term="TEXT"/>`.

## Dependencies & Setup
- Configure Elasticsearch host in `settings.py` via `ELASTICSEARCH_DSL` envs.
- Index creation/population (after DB is ready):
  - `python manage.py search_index --rebuild -f --models thesaurus`

## Notes & Edge Cases
- Wildcards only apply to `term_string` (quick) and `term_string__full_field` (exact).
- When no `lang` is provided, Spanish entries are excluded (`must_not es-es`).
- Results depend on ES analyzers; `term_string.raw` must be a keyword subfield to sort correctly.
- If a term has multiple tree numbers, only the first (lowest) is returned.

## Examples
- JSON
  - Request: `curl -s 'http://localhost:8000/api/thesaurus/quickterm/?query=acute%20abdomen&lang=en&count=3' -H 'Accept: application/json'`
  - Response (shape):
    {
      "meta": { "limit": 3, "offset": 0, "total_count": 3 },
      "objects": [
        { "item": { "attr": { "id": "A01.111.222", "term": "Acute Abdomen" } } },
        { "item": { "attr": { "id": "C23.300.937", "term": "/diagnosis" } } },
        { "item": { "attr": { "id": "A01.111.222", "term": "Acute Abdominal Pain" } } }
      ]
    }

- XML (default format)
  - Request: `curl -s 'http://localhost:8000/api/thesaurus/quickterm/?query=acute%20abdomen&lang=en&count=3'`
  - Response (shape):
    <?xml version="1.0" encoding="utf-8"?>
    <DeCSTermService version="1.0">
      <Result count="3" total="3">
        <item id="A01.111.222" term="Acute Abdomen"/>
        <item id="C23.300.937" term="/diagnosis"/>
        <item id="A01.111.222" term="Acute Abdominal Pain"/>
      </Result>
    </DeCSTermService>
