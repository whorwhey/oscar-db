# Thin CLI runner for the queries/ collection: loads a named .sql file and
# runs it against oscars.db with one LIKE-wrapped search term.
# Run: uv run src/query.py <query-name> <search-term>
#   uv run src/query.py person-history "Daniel Day-Lewis"
#   uv run src/query.py title-search "Titanic"

import difflib
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

DB_PATH = "oscars.db"
QUERIES_DIR = Path("queries")

# query-name -> (sql filename, entity table, searched column). The table +
# column let us give match-quality feedback (separator note, did-you-mean).
QUERIES = {
    "person-history": ("person_history.sql", "people", "name"),
    "title-search": ("title_search.sql", "films", "title"),
}


def build_pattern(term):
    """Turn a search term into a forgiving LIKE pattern.

    Split on any non-word character and rejoin the word-tokens with '%', so
    the gaps between words match any separator in the data ('Daniel Day Lewis'
    finds 'Daniel Day-Lewis'). Falls back to the raw term if it has no word
    characters at all (e.g. a search that is only punctuation)."""
    tokens = [t for t in re.split(r"\W+", term) if t]
    if not tokens:
        return f"%{term}%"
    return "%" + "%".join(tokens) + "%"


def is_loose_match(term, values):
    """True if `term` is not a literal (case-insensitive) substring of any of
    the matched `values` — i.e. it only matched by loosening separators."""
    needle = term.lower()
    return not any(needle in v.lower() for v in values if v is not None)


def suggest(conn, table, column, term):
    """Closest existing values to `term` (case-insensitive), for did-you-mean.
    Returns display-cased strings, best first, or []."""
    rows = conn.execute(f"SELECT DISTINCT {column} FROM {table}").fetchall()
    by_lower = {r[0].lower(): r[0] for r in rows if r[0] is not None}
    hits = difflib.get_close_matches(term.lower(), by_lower.keys(), n=2, cutoff=0.6)
    return [by_lower[h] for h in hits]


def usage():
    print("usage: uv run src/query.py <query-name> <search-term>")
    print(f"  query-name: {' | '.join(QUERIES)}")


def main():
    if len(sys.argv) != 3:
        usage()
        sys.exit(1)

    query_name, search_term = sys.argv[1], sys.argv[2]
    if query_name not in QUERIES:
        print(f"unknown query: {query_name}")
        usage()
        sys.exit(1)

    sql_file, table, column = QUERIES[query_name]
    sql = (QUERIES_DIR / sql_file).read_text()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    result = pd.read_sql_query(sql, conn, params=(build_pattern(search_term),))

    if result.empty:
        hits = suggest(conn, table, column, search_term)
        if hits:
            print(f"no matches for {search_term!r}. Did you mean: {', '.join(hits)}?")
        else:
            print(f"no matches for {search_term!r}")
    else:
        if is_loose_match(search_term, result[column]):
            print(f"note: no exact match for {search_term!r} — showing loose "
                  "matches (spacing and punctuation ignored)")
        print(result.to_string(index=False))

    conn.close()


if __name__ == "__main__":
    main()
