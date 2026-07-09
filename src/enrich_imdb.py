# Re-runnable IMDb sync.
#   films  <- title.basics: release_year, original_title, runtime_minutes;
#             reports (does not write) title divergence from primaryTitle.
#   people <- name.basics:  birth_year, death_year (kind='person' only;
#             companies are absent from name.basics by design);
#             reports (does not write) name divergence from primaryName;
#             persons with no imdb_id are counted only -- the curated
#             review list data/people_no_imdb_id.txt is maintained
#             separately and must not be clobbered here.
# Datasets from https://datasets.imdbws.com/ -- download separately,
# not committed (large, re-downloadable, see .gitignore).
#
# Keyed on imdb_id (tconst/nconst), per the enrichment-persistence decision
# in CLAUDE.md: oscars.db is persisted state, not rebuilt from ingest.py, so
# this updates the existing db in place rather than re-ingesting.
# Only non-NULL IMDb values are written: a value missing at IMDb (\N) never
# overwrites what the db already holds (e.g. hand-entered fixes).

import gzip
import sqlite3


def normalize(s: str) -> str:
    return " ".join(s.split()).casefold()


def to_none(field: str) -> str | None:
    return None if field == r"\N" else field


def load_matches(tsv_gz_path, id_column, wanted_ids: set[str]) -> dict[str, dict]:
    """id -> {column: value-or-None}, for rows whose id_column is in wanted_ids."""
    matches = {}
    with gzip.open(tsv_gz_path, "rt", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        id_index = header.index(id_column)
        for line in f:
            fields = line.rstrip("\n").split("\t")
            row_id = fields[id_index]
            if row_id not in wanted_ids:
                continue
            matches[row_id] = {name: to_none(field) for name, field in zip(header, fields)}
    return matches


def write_report(path, header, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for row in rows:
            f.write("\t".join(str(value) for value in row) + "\n")


def sync_columns(cur, table, id_column, row_id, columns, match, int_columns):
    """UPDATE one row's enrichment columns from an IMDb match; count writes."""
    written = []
    for column, field in columns.items():
        if match[field] is not None:
            value = int(match[field]) if column in int_columns else match[field]
            cur.execute(
                f"UPDATE {table} SET {column} = ? WHERE {id_column} = ?",
                (value, row_id),
            )
            written.append(column)
    return written


def sync_films(cur, tsv_gz_path="data/title.basics.tsv.gz"):
    films = cur.execute(
        "SELECT film_id, title, imdb_id FROM films WHERE imdb_id IS NOT NULL"
    ).fetchall()
    matches = load_matches(tsv_gz_path, "tconst", {i for _, _, i in films})

    columns = {"release_year": "startYear", "original_title": "originalTitle",
               "runtime_minutes": "runtimeMinutes"}
    updated = dict.fromkeys(columns, 0)
    unmatched = []
    title_mismatches = []
    for film_id, title, imdb_id in films:
        if imdb_id not in matches:
            unmatched.append((film_id, title, imdb_id))
            continue
        m = matches[imdb_id]
        for column in sync_columns(cur, "films", "film_id", film_id, columns, m,
                                   int_columns={"release_year", "runtime_minutes"}):
            updated[column] += 1
        if normalize(m["primaryTitle"]) != normalize(title):
            title_mismatches.append((film_id, title, m["primaryTitle"], imdb_id))

    print(f"-- films (title.basics) --")
    print(f"films with imdb_id: {len(films)}")
    for column, count in updated.items():
        print(f"{column} updated: {count}")
    print(f"unmatched (imdb_id not found in title.basics): {len(unmatched)}")
    for film_id, title, imdb_id in unmatched:
        print(f"  {film_id}\t{title!r}\t{imdb_id}")

    print(f"title mismatches (report only, not written): {len(title_mismatches)}")
    for film_id, ours, theirs, imdb_id in title_mismatches:
        print(f"  {film_id}\t{imdb_id}\tours={ours!r}\tIMDb={theirs!r}")


def sync_people(cur, tsv_gz_path="data/name.basics.tsv.gz"):
    people = cur.execute(
        "SELECT person_id, name, imdb_id FROM people"
        " WHERE imdb_id IS NOT NULL AND kind = 'person'"
    ).fetchall()
    matches = load_matches(tsv_gz_path, "nconst", {i for _, _, i in people})

    columns = {"birth_year": "birthYear", "death_year": "deathYear"}
    updated = dict.fromkeys(columns, 0)
    unmatched = []
    name_mismatches = []
    for person_id, name, imdb_id in people:
        if imdb_id not in matches:
            unmatched.append((person_id, name, imdb_id))
            continue
        m = matches[imdb_id]
        for column in sync_columns(cur, "people", "person_id", person_id, columns, m,
                                   int_columns={"birth_year", "death_year"}):
            updated[column] += 1
        if normalize(m["primaryName"]) != normalize(name):
            name_mismatches.append((person_id, name, m["primaryName"], imdb_id))

    (no_imdb,) = cur.execute(
        "SELECT COUNT(*) FROM people WHERE imdb_id IS NULL AND kind = 'person'"
    ).fetchone()

    print(f"\n-- people (name.basics) --")
    print(f"persons with imdb_id: {len(people)}")
    for column, count in updated.items():
        print(f"{column} updated: {count}")
    print(f"unmatched (imdb_id not found in name.basics): {len(unmatched)}")
    for person_id, name, imdb_id in unmatched:
        print(f"  {person_id}\t{name!r}\t{imdb_id}")

    print(f"persons without imdb_id: {no_imdb}"
          f" (review list: data/people_no_imdb_id.txt, maintained separately)")

    write_report("data/name_review.txt", "person_id\timdb_id\tours\tIMDb",
                 [(person_id, imdb_id, ours, theirs)
                  for person_id, ours, theirs, imdb_id in name_mismatches])
    print(f"name mismatches (report only, not written): {len(name_mismatches)}"
          f" -> data/name_review.txt")


def main(db_path="data/oscars.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    sync_films(cur)
    sync_people(cur)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
