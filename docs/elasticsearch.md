# Understanding Elasticsearch in the Provided Python Script

This document explains how Elasticsearch is used in the Python script
you provided, written for search functionalities. It covers both the
**general role of Elasticsearch** and the **specific case of
`op_prefix = "quick"`**.

------------------------------------------------------------------------

## 1. What is Elasticsearch?

-   **Definition**: Elasticsearch is an open-source search and analytics
    engine, often described as a "Google-like" system for custom
    applications.
-   **Data format**: Stores data as **JSON documents**, grouped in
    **indexes** (like databases).
-   **Querying**: Supports flexible queries:
    -   Exact matches (`term`)
    -   Full-text searches (`match`)
    -   Wildcards (`*` for partial matches)
    -   Boolean logic (AND, OR, NOT)
-   **Performance**: Designed for **very fast text searches**, even
    across millions of records.

------------------------------------------------------------------------

## 2. What is `elasticsearch_dsl`?

-   A **Python client library** that simplifies writing Elasticsearch
    queries.
-   `Q`: used to define query clauses.
-   `Search`: used to run searches against indexes.

This avoids manually constructing JSON queries.

------------------------------------------------------------------------

## 3. How the Script Uses Elasticsearch

### a) Query construction

-   Function **`get_search_q`** generates queries and decides which
    indexes to search.
-   Supports prefixes like `101`, `401`, `"words"`, and `"quick"`.
-   Builds queries with `match`, `wildcard`, and `term` filters.

### b) Executing searches

-   **`execute_simple_search`**: runs queries across indexes, returns
    cleaned results (`identifier`, `term_type`).
-   **`execute_quick_search`**: optimized for `"quick"` searches,
    returns preferred and synonym terms.

### c) Complex boolean queries

-   **`complex_search`**: handles AND, OR, AND NOT logic recursively
    across multiple conditions.

### d) Parsing input

-   **`f_parse`**: converts a string like
    `"401 Supply OR (401 Rural AND 401 Water)"` into a structured list
    the code can use.

------------------------------------------------------------------------

## 4. Indexes Used in the Project

-   `descriptor_term`: stores **preferred terms**.
-   `qualifier_term`: stores **qualifier terms** (sub-terms).
-   `previous_term`: stores **historical terms**.
-   `descriptor_treenumber` and `qualifier_treenumber`: tree-structured
    indexes.

------------------------------------------------------------------------

## 5. Focus: `op_prefix = "quick"`

### Purpose

-   **"Quick search"** mode: fast lookup of **preferred terms and
    synonyms**.
-   Searches only in `descriptor_term` and `qualifier_term`.

### Query building

1.  **Wildcard support**:

    ``` python
    if "*" in text:
        must_words = [Q("wildcard", term_string=text)]
    else:
        must_words = [Q("match", term_string={"query": text, "operator": "AND"})]
    ```

2.  **Language handling**:

    -   If no `lang_code`: exclude Spanish
        (`must_not language_code="es-es"`).
    -   If `lang_code` is given: use it as a filter.

3.  **Return value**:

    ``` python
    return dict(index=["descriptor_term", "qualifier_term"], query=query_q)
    ```

### Execution

-   **`execute_quick_search`** runs the query:

    -   Default: only **2 results** (fast response).
    -   With sorting: up to **1000 results**, sorted alphabetically
        (`term_string.raw`).

-   Results look like:

    ``` python
    [
      {"identifier": 123, "term_type": "descriptor", "term_string": "Heart Disease"},
      {"identifier": 456, "term_type": "qualifier", "term_string": "Ischemic Heart Disease"}
    ]
    ```

### ✅ Summary for `"quick"`

-   Searches **descriptors + qualifiers** only.
-   Supports **wildcards** (`*`).
-   Excludes Spanish if no `lang_code`.
-   Returns **preferred + synonym terms**, with deduplication.
-   Limits results for speed unless sorted.

------------------------------------------------------------------------

## 6. End-to-End Example

Query:

    op_prefix = "quick"
    text = "heart disease"
    lang_code = None

Steps: 1. `get_search_q` builds: - Query: match `"heart disease"` (AND
operator). - Filter: exclude Spanish. - Indexes: `descriptor_term`,
`qualifier_term`.

2.  Passed to `execute_quick_search`:
    -   Executes against Elasticsearch.
    -   Retrieves hits.
3.  Returns cleaned results with identifier, type, and term string.

------------------------------------------------------------------------

# Final Notes

-   The script acts as a **search layer on top of Elasticsearch**.
-   `"quick"` mode is a **fast, simplified search** designed for
    descriptors and qualifiers only.
-   It balances **speed** (default 2 results) with **flexibility**
    (sorting for full lists).
