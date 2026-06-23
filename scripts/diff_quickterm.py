#!/usr/bin/env python3
"""
One-shot script to compare the old decsQuickTerm API with the new quickterm API.
Parses XML from both endpoints and diffs the ordered list of (tree_number, term) pairs.

Usage:
    python scripts/diff_quickterm.py [--new-base URL]

By default:
    Old API: https://srv.bvsalud.org/decsQuickTerm/search
    New API: http://localhost:8000/api/thesaurus/quickterm/

Override the new API base with --new-base, e.g.:
    python scripts/diff_quickterm.py --new-base https://decs-api.teste.bvsalud.org/api/thesaurus/quickterm/
"""

import argparse
import sys
from difflib import unified_diff
from xml.etree import ElementTree

import requests

OLD_API = "https://srv.bvsalud.org/decsQuickTerm/search"
NEW_API_DEFAULT = "http://decs-api.teste.bvsalud.org/api/thesaurus/quickterm/"

QUERIES = [
    "sindrome respiratoria",   # canonical regression case (multi-word)
    "coronavirus",             # single word, many hits
    "dengue",                  # short, high-frequency term
    "insuficiencia cardiaca",  # multi-word, common
    "covid",                   # acronym
]


def fetch_items(url, query, timeout=30):
    """Fetch XML from endpoint and return list of (id, term) tuples."""
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "pt-BR,pt;q=0.9,en;q=0.8",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    resp = requests.get(url, params={"query": query}, timeout=timeout,
                        headers=headers)
    resp.raise_for_status()

    root = ElementTree.fromstring(resp.content)
    items = []
    for item in root.iter("item"):
        tree_id = item.get("id", "")
        term = item.get("term", "")
        items.append((tree_id, term))
    return items


def format_items(items):
    """Format item list as numbered lines for diffing."""
    lines = []
    for i, (tree_id, term) in enumerate(items, 1):
        lines.append(f"{i:4d}  {tree_id}  {term}")
    return lines


def main():
    parser = argparse.ArgumentParser(description="Diff old vs new quickterm API")
    parser.add_argument("--new-base", default=NEW_API_DEFAULT,
                        help="Base URL for the new API (default: %(default)s)")
    parser.add_argument("--queries", nargs="*", default=None,
                        help="Custom queries to test (default: built-in list)")
    args = parser.parse_args()

    queries = args.queries if args.queries else QUERIES
    all_pass = True

    for query in queries:
        print(f"\n{'='*72}")
        print(f"  Query: {query!r}")
        print(f"{'='*72}")

        try:
            old_items = fetch_items(OLD_API, query)
        except Exception as e:
            print(f"  [ERROR] Old API failed: {e}")
            all_pass = False
            continue

        try:
            new_items = fetch_items(args.new_base, query)
        except Exception as e:
            print(f"  [ERROR] New API failed: {e}")
            all_pass = False
            continue

        old_lines = format_items(old_items)
        new_lines = format_items(new_items)

        if old_lines == new_lines:
            print(f"  PASS — {len(old_items)} items, order matches exactly")
        else:
            all_pass = False
            print(f"  FAIL — old has {len(old_items)} items, new has {len(new_items)} items")
            print()

            diff = unified_diff(
                old_lines, new_lines,
                fromfile="old API", tofile="new API",
                lineterm=""
            )
            for line in diff:
                print(f"  {line}")

        # Also show set differences (missing / extra terms)
        old_set = set(old_items)
        new_set = set(new_items)
        missing = old_set - new_set
        extra = new_set - old_set

        if missing:
            print(f"\n  Missing in new API ({len(missing)}):")
            for tree_id, term in sorted(missing):
                print(f"    - {tree_id}  {term}")

        if extra:
            print(f"\n  Extra in new API ({len(extra)}):")
            for tree_id, term in sorted(extra):
                print(f"    + {tree_id}  {term}")

    print(f"\n{'='*72}")
    if all_pass:
        print("  ALL QUERIES PASSED")
    else:
        print("  SOME QUERIES FAILED — see diff above")
    print(f"{'='*72}\n")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
