## What I found

The cluster (ES 9.4.4) is green and all five indexes exist, with doc counts matching the source DB **exactly**:

| index                   | ES docs | MySQL rows |     |
| ----------------------- | ------- | ---------- | --- |
| `descriptor_term`       | 779,697 | 779,697    | ✅  |
| `descriptor_treenumber` | 74,822  | 74,822     | ✅  |
| `previous_term`         | 28,000  | 28,000     | ✅  |
| `qualifier_term`        | 2,563   | 2,563      | ✅  |
| `qualifier_treenumber`  | 362     | 362        | ✅  |

Mappings are also correct — every field from `app/thesaurus/documents.py` is present with the right analyzers and normalizers.

**But every document is empty.** Each hit returns `"_source": {}`, and an `exists` query on `term_string`, `language_code`, or `tree_number` returns **0** across the board. Note `descriptor_term` is only 8.3 MB for 780k docs (~11 bytes/doc). Your rebuild indexed ~886k empty shells.

## Root cause

A silent regression in **elasticsearch 9.4.0**, which `pyproject.toml:16` pulls in via `elasticsearch~=9.5.0`.

`AttrDict.__setattr__` (`elasticsearch/dsl/utils.py:232`) now routes an attribute into the internal `_d_` dict unless the class attribute is a property with an `fset`. That swallows this line in `django_elasticsearch_dsl/documents.py:66`:

```python
self._prepared_fields = self.init_prepare()
```

`_prepared_fields` has a plain class-level default of `[]`, so the write lands in `_d_` while reads resolve to the class attribute `[]`. `prepare()` then iterates nothing and returns `{}` for every object.

I reproduced it in a clean venv: `init_prepare()` returns the correct field list, but `d._prepared_fields` reads back as `[]` and `prepare(obj)` returns `{}`. Bisected across releases — **9.0.0–9.3.0 OK, 9.4.0 and 9.5.0 broken**. This came in with the Django 5.2/Python 3.14 upgrade (1b724d4).

The reason it looks like "empty or incomplete" rather than a crash: the rebuild reports success, mappings are built from the class definition (so they're fine), and the doc count is driven by the queryset (so it's exact). Only the payload is missing.

## Fix

django-elasticsearch-dsl 9.0 is the latest release — no upstream fix exists. Two options:

1. **Pin `elasticsearch~=9.3.0`** in `pyproject.toml`, then `make deps_lock`. One-line change, no app code touched. Downside: `make deps_upgrade` can silently reintroduce it.
2. **Keep 9.5 and add a base Document class** in `documents.py` that the five documents inherit from:
   ```python
   def __init__(self, related_instance_to_ignore=None, **kwargs):
       super().__init__(related_instance_to_ignore=related_instance_to_ignore, **kwargs)
       object.__setattr__(self, "_prepared_fields", self.init_prepare())
   ```
   I verified this restores `prepare()` to `{'term_string': 'Cardiologia', 'language_code': 'pt-br'}`.

I'd go with option 1 now to unblock the test environment, since it's lower risk. Either way you'll need to re-run `make prod_search_index_build` afterwards — the current data is unrecoverable. Verify the rebuild with `curl 'http://172.17.1.93:9200/descriptor_term/_search?size=1'` and confirm `_source` is non-empty; the doc count alone won't tell you.


## Implementation of option 2

Implemented and verified.

## Changes

**`app/thesaurus/documents.py`** — added a `BaseDocument` class that all five documents now inherit from instead of `Document`:

```python
def __init__(self, related_instance_to_ignore=None, **kwargs):
	super().__init__(related_instance_to_ignore=related_instance_to_ignore, **kwargs)
	object.__setattr__(self, '_prepared_fields', self.init_prepare())
```

**`app/thesaurus/tests.py`** — added `PreparedFieldsTest`, which asserts that every registered document's `_prepared_fields` covers its full mapping. It needs no database or live cluster, so it runs under `make test`.

## Why this holds across future versions

`object.__setattr__` writes into the instance `__dict__`. Since `_prepared_fields` is a plain list class attribute, not a data descriptor, instance `__dict__` always takes precedence on lookup — regardless of what `AttrDict.__setattr__` does in any given release. If upstream later fixes the setter, the assignment simply becomes redundant rather than conflicting. No `elasticsearch` pin needed, so `make deps_upgrade` stays unconstrained.

I verified this on a stubbed harness running the real `documents.py`:

|                       | elasticsearch 9.3.0 | elasticsearch 9.5.0         |
| --------------------- | ------------------- | --------------------------- |
| committed code (HEAD) | —                   | ❌ all 5 → `prepare() = {}` |
| with `BaseDocument`   | ✅ all 5 populated  | ✅ all 5 populated          |

The pre-fix run reproduced your exact production symptom — all five documents returning `{}` — which confirms the diagnosis end-to-end rather than just in the isolated repro. Sample output now:

```
DescriptorTermDocument  prepare()={'term_string': 'Cardiologia', 'language_code': 'pt-br',
                                   'record_preferred_term': 'Y', 'term_thesaurus': '1', 'status': 1, ...}
```

Two notes on what I could **not** verify locally: `mysqlclient` won't build on this machine (no `libmysqlclient` headers), so `uv sync` fails and I couldn't run the actual Django test suite or exercise `search_index` against real model instances — the stub supplies its own models. The `identifier`/`identifier_concept` object fields show as `{}` in the harness only because the stub instances have null FKs; they'll populate from real rows.

Next steps on your side: rebuild the image (the code change needs to land in the container), then re-run `make prod_search_index_build`. The current 886k empty documents will be replaced by the `--rebuild`. Confirm with:

```bash
curl 'http://172.17.1.93:9200/descriptor_term/_search?size=1&pretty'
```

`_source` must be non-empty — the doc count will look correct either way.

I haven't committed anything; the changes are in the working tree on `rc/5.2`.
