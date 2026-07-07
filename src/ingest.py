# Parsing/insertion helpers for data/oscars.tsv -> data/oscars.db.
# See schema.md / data_notes.md for the design this follows.

import sqlite3
from pathlib import Path


def parse_row(line: str, columns: list[str]) -> dict[str, str]:
    # trailing empty TSV fields get stripped by the source export, so rows
    # are ragged; pad to align with `columns` instead of letting zip() truncate
    values = line.strip("\n").split("\t")
    missing = len(columns) - len(values)
    values = values + [""] * missing
    return dict(zip(columns, values))


def parse_winner(value: str) -> int:
    return 1 if value == "True" else 0


def to_null(value: str) -> str | None:
    return None if value in ("?", "") else value


def split_pipe(value: str) -> list[str]:
    # "".split("|") -> [""], not []; empty must mean zero values, not one blank value
    return value.split("|") if value else []


def normalize_title(s: str) -> str:
    return " ".join(s.split())


def align_ids(names: list[str], ids: list[str]) -> list[str]:
    # ids is sometimes shorter than names (missing entirely, not even '?'
    # per entry); pad with '?' so every name still gets an (name, id) pair
    missing = len(names) - len(ids)
    return ids + ["?"] * missing


# ensure_film/ensure_person share one pattern: match on imdb_id when known
# (reliable, external); fall back to normalized text only when the id is
# unknown ('?'), since that's the only signal left to recognize a repeat.
def ensure_film(cursor, title, imdb_id_raw, film_by_imdb, film_by_title):
    imdb_id = to_null(imdb_id_raw)

    if imdb_id is not None:
        if imdb_id in film_by_imdb:
            return film_by_imdb[imdb_id]
        cursor.execute(
            "INSERT INTO films (title, imdb_id) VALUES (?, ?)", (title, imdb_id)
        )
        film_id = cursor.lastrowid
        film_by_imdb[imdb_id] = film_id
        return film_id

    key = normalize_title(title)
    if key in film_by_title:
        return film_by_title[key]
    cursor.execute("INSERT INTO films (title) VALUES (?)", (title,))
    film_id = cursor.lastrowid
    film_by_title[key] = film_id
    return film_id


def derive_kind(imdb_id: str | None) -> str:
    # unmatched entities are overwhelmingly obscure individuals -> default 'person'
    if imdb_id is not None and imdb_id.startswith("co"):
        return "company"
    return "person"


def ensure_person(cursor, name, imdb_id_raw, person_by_imdb, person_by_title):
    imdb_id = to_null(imdb_id_raw)
    kind = derive_kind(imdb_id)

    if imdb_id is not None:
        if imdb_id in person_by_imdb:
            return person_by_imdb[imdb_id]
        cursor.execute(
            "INSERT INTO people (name, imdb_id, kind) VALUES (?, ?, ?)",
            (name, imdb_id, kind),
        )
        person_id = cursor.lastrowid
        person_by_imdb[imdb_id] = person_id
        return person_id

    key = normalize_title(name)
    if key in person_by_title:
        return person_by_title[key]
    cursor.execute("INSERT INTO people (name, kind) VALUES (?, ?)", (name, kind))
    person_id = cursor.lastrowid
    person_by_title[key] = person_id
    return person_id


def ensure_ceremony(cursor, ceremony_raw, year_label, seen_ceremonies):
    ceremony = int(ceremony_raw)
    if ceremony in seen_ceremonies:
        return
    cursor.execute(
        "INSERT INTO ceremonies (ceremony, year_label) VALUES (?, ?)",
        (ceremony, year_label),
    )
    seen_ceremonies.add(ceremony)


def load_categories(cursor, seed_path="data/categories_seed.tsv") -> dict[str, int]:
    """Insert curated categories; return source_name -> category_id."""
    category_by_name = {}
    with open(seed_path) as f:
        columns = f.readline().strip("\n").split("\t")
        for line in f:
            row = parse_row(line, columns)
            cursor.execute(
                "INSERT INTO categories (source_name, award_group, class) VALUES (?, ?, ?)",
                (row["source_name"], row["award_group"], row["class"]),
            )
            category_by_name[row["source_name"]] = cursor.lastrowid
    return category_by_name


def main(
    tsv_path="data/oscars.tsv",
    db_path="data/oscars.db",
    schema_path="schema.sql",
):
    Path(db_path).unlink(missing_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(Path(schema_path).read_text())
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        seen_ceremonies = set()
        category_by_name = load_categories(cursor)
        film_by_imdb = {}
        film_by_title = {}
        person_by_imdb = {}
        person_by_name = {}

        with open(tsv_path) as f:
            columns = f.readline().strip("\n").split("\t")

            for line in f:
                row = parse_row(line, columns)

                ensure_ceremony(cursor, row["Ceremony"], row["Year"], seen_ceremonies)
                try:
                    category_id = category_by_name[row["CanonicalCategory"]]
                except KeyError:
                    raise ValueError(
                        f"unclassified category {row['CanonicalCategory']!r} "
                        "— add it to data/categories_seed.tsv"
                    ) from None

                cursor.execute(
                    """
                    INSERT INTO nominations
                        (ceremony, category_id, raw_category, official_name,
                         is_winner, detail, note, citation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(row["Ceremony"]),
                        category_id,
                        row["Category"],
                        to_null(row["Name"]),
                        parse_winner(row["Winner"]),
                        to_null(row["Detail"]),
                        to_null(row["Note"]),
                        to_null(row["Citation"]),
                    ),
                )
                nomination_id = cursor.lastrowid

                film_names = split_pipe(row["Film"])
                film_ids = align_ids(film_names, split_pipe(row["FilmId"]))
                for title, imdb_id_raw in zip(film_names, film_ids):
                    film_id = ensure_film(
                        cursor, title, imdb_id_raw, film_by_imdb, film_by_title
                    )
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO nomination_films (nomination_id, film_id)
                        VALUES (?, ?)
                        """,
                        (nomination_id, film_id),
                    )

                nominee_names = split_pipe(row["Nominees"])
                nominee_ids = align_ids(nominee_names, split_pipe(row["NomineeIds"]))
                for name, imdb_id_raw in zip(nominee_names, nominee_ids):
                    person_id = ensure_person(
                        cursor, name, imdb_id_raw, person_by_imdb, person_by_name
                    )
                    # OR IGNORE: source can repeat one entity within a row
                    # (same imdb_id, different display names) -> exact
                    # duplicate junction row, rejected by the composite PK
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO nomination_people (nomination_id, person_id)
                        VALUES (?, ?)
                        """,
                        (nomination_id, person_id),
                    )

        # every seeded category must have matched at least one source row;
        # an unused seed row means a typo'd source_name (the ValueError in
        # the loop only catches the other direction: data with no seed entry)
        cursor.execute(
            """
            SELECT source_name FROM categories
            WHERE category_id NOT IN (SELECT category_id FROM nominations)
            """
        )
        unused = [name for (name,) in cursor.fetchall()]
        if unused:
            raise ValueError(f"seeded categories matched no rows: {unused}")

        conn.commit()

        for table in ("ceremonies", "categories", "nominations", "films",
                      "people", "nomination_films", "nomination_people"):
            (count,) = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            print(f"{table:>18}: {count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

