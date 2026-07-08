# One-off enrichment: films.release_year from IMDb's title.basics dataset.
# https://datasets.imdbws.com/title.basics.tsv.gz -- download separately,
# not committed (213MB, re-downloadable, see .gitignore).
#
# Keyed on imdb_id (tconst), per the enrichment-persistence decision in
# CLAUDE.md: oscars.db is persisted state, not rebuilt from ingest.py, so
# this updates the existing db in place rather than re-ingesting.

import gzip
import sqlite3
from pathlib import Path


def normalize(s: str) -> str:
    return " ".join(s.split()).casefold()


def load_matches(tsv_gz_path, wanted_ids: set[str]) -> dict[str, tuple[str, int | None]]:
    """tconst -> (primaryTitle, startYear or None), for tconst in wanted_ids."""
    matches = {}
    with gzip.open(tsv_gz_path, "rt", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        idx = {name: i for i, name in enumerate(header)}
        for line in f:
            fields = line.rstrip("\n").split("\t")
            tconst = fields[idx["tconst"]]
            if tconst not in wanted_ids:
                continue
            primary_title = fields[idx["primaryTitle"]]
            start_year = fields[idx["startYear"]]
            year = int(start_year) if start_year != r"\N" else None
            matches[tconst] = (primary_title, year)
    return matches


def main(db_path="data/oscars.db", tsv_gz_path="data/title.basics.tsv.gz"):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    films = cur.execute(
        "SELECT film_id, title, imdb_id FROM films WHERE imdb_id IS NOT NULL"
    ).fetchall()
    wanted_ids = {imdb_id for _, _, imdb_id in films}

    matches = load_matches(tsv_gz_path, wanted_ids)

    unmatched = []
    title_mismatches = []
    updated = 0
    for film_id, title, imdb_id in films:
        if imdb_id not in matches:
            unmatched.append((film_id, title, imdb_id))
            continue
        primary_title, year = matches[imdb_id]
        if year is not None:
            cur.execute(
                "UPDATE films SET release_year = ? WHERE film_id = ?", (year, film_id)
            )
            updated += 1
        if normalize(primary_title) != normalize(title):
            title_mismatches.append((film_id, title, primary_title, imdb_id))

    conn.commit()
    conn.close()

    print(f"films with imdb_id: {len(films)}")
    print(f"release_year updated: {updated}")
    print(f"unmatched (imdb_id not found in title.basics): {len(unmatched)}")
    for film_id, title, imdb_id in unmatched:
        print(f"  {film_id}\t{title!r}\t{imdb_id}")

    print(f"\ntitle mismatches (report only, not written): {len(title_mismatches)}")
    for film_id, ours, theirs, imdb_id in title_mismatches:
        print(f"  {film_id}\t{imdb_id}\tours={ours!r}\tIMDb={theirs!r}")


if __name__ == "__main__":
    main()
