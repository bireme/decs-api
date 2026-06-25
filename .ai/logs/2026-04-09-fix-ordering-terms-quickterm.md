## Changes made

### 1. Fixed "top 2 most relevant" query (`esearch_functions.py:48-72`)
- The `'103'` op_prefix now uses `match_phrase` on the analyzed `term_string` field (standard tokenizer) instead of `match` on `term_string.full_field` (keyword tokenizer).
- Added `should` boosts for `match_phrase_prefix` (shorter terms with query at the start rank higher) and exact `term` match on `.raw`.
- This means multi-word queries like `"sindrome respiratoria"` will now actually return hits (e.g., "Síndrome Respiratória Aguda Grave").

### 2. Case-sensitive byte-order sort (`documents.py` + `esearch_functions.py:237`)
- Added `term_string.sort` — a `KeywordField` with **no normalizer** — to both `DescriptorTermDocument` and `QualifierTermDocument`.
- Changed `execute_quick_search` to sort on `term_string.sort` instead of `term_string.raw` (which had a lowercase normalizer).
- **Requires reindexing** (`python manage.py search_index --rebuild`) to populate the new subfield.

### 3. Removed dedup of top-2 from alphabetical list (`thesaurus_quickterm_api.py:120-121`)
- Changed from filtering (`if term not in items`) to `items.extend(terms_alph)`, so the top-2 descriptors appear both at the beginning and at their alphabetical position, matching the old API.

### 4. Updated docs (`docs/quickterm-search-issues.md`)
- Marked issue #2 (relevance ordering) as resolved.

### Next steps
- **Reindex Elasticsearch** to create the new `term_string.sort` subfield:
  ```bash
  python manage.py search_index --rebuild
  ```
- Run the verification diff script from the plan against the old API to confirm ordering matches.