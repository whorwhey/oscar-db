# Re-runnable IMDb sync: films.release_year, original_title, runtime_minutes
# from IMDb's title.basics dataset. Also reports (does not write) title
# divergence from primaryTitle.
# https://datasets.imdbws.com/title.basics.tsv.gz -- download separately,
# not committed (213MB, re-downloadable, see .gitignore).
#
# Keyed on imdb_id (tconst), per the enrichment-persistence decision in
# CLAUDE.md: oscars.db is persisted state, not rebuilt from ingest.py, so
# this updates the existing db in place rather than re-ingesting.
# Only non-NULL IMDb values are written: a value missing at IMDb (\N) never
# overwrites what the db already holds (e.g. hand-entered fixes).

import gzip
import sqlite3


def normalize(s: str) -> str:
    return " ".join(s.split()).casefold()


def to_none(field: str) -> str | None:
    return None if field == r"\N" else field


def load_matches(tsv_gz_path, wanted_ids: set[str]) -> dict[str, dict]:
    """tconst -> {primary_title, original_title, year, runtime}, for tconst in wanted_ids."""
    matches = {}
    with gzip.open(tsv_gz_path, "rt", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        idx = {name: i for i, name in enumerate(header)}
        for line in f:
            fields = line.rstrip("\n").split("\t")
            tconst = fields[idx["tconst"]]
            if tconst not in wanted_ids:
                continue
            start_year = to_none(fields[idx["startYear"]])
            runtime = to_none(fields[idx["runtimeMinutes"]])
            matches[tconst] = {
                "primary_title": fields[idx["primaryTitle"]],
                "original_title": to_none(fields[idx["originalTitle"]]),
                "year": int(start_year) if start_year is not None else None,
                "runtime": int(runtime) if runtime is not None else None,
            }
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

    columns = {"release_year": "year", "original_title": "original_title",
               "runtime_minutes": "runtime"}
    updated = dict.fromkeys(columns, 0)
    unmatched = []
    title_mismatches = []
    for film_id, title, imdb_id in films:
        if imdb_id not in matches:
            unmatched.append((film_id, title, imdb_id))
            continue
        m = matches[imdb_id]
        for column, key in columns.items():
            if m[key] is not None:
                cur.execute(
                    f"UPDATE films SET {column} = ? WHERE film_id = ?",
                    (m[key], film_id),
                )
                updated[column] += 1
        if normalize(m["primary_title"]) != normalize(title):
            title_mismatches.append((film_id, title, m["primary_title"], imdb_id))

    conn.commit()
    conn.close()

    print(f"films with imdb_id: {len(films)}")
    for column, count in updated.items():
        print(f"{column} updated: {count}")
    print(f"unmatched (imdb_id not found in title.basics): {len(unmatched)}")
    for film_id, title, imdb_id in unmatched:
        print(f"  {film_id}\t{title!r}\t{imdb_id}")

    print(f"\ntitle mismatches (report only, not written): {len(title_mismatches)}")
    for film_id, ours, theirs, imdb_id in title_mismatches:
        print(f"  {film_id}\t{imdb_id}\tours={ours!r}\tIMDb={theirs!r}")


if __name__ == "__main__":
    main()
