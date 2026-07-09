# Correctness checks for data/oscars.db.
# Run: uv run src/verify.py
# Sections: structural integrity, aggregate sanity, IMDb enrichment,
# known-fact spot checks, TSV round-trip sample. Prints one line per check;
# exits nonzero on any failure.

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ingest import parse_row, to_null, parse_winner, split_pipe, align_ids

DB_PATH = "data/oscars.db"
TSV_PATH = "data/oscars.tsv"

failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        failures.append(name)


def section(title):
    print(f"\n-- {title} --")


def structural(cur):
    section("structural")

    violations = cur.execute("PRAGMA foreign_key_check").fetchall()
    check("no foreign key violations", not violations, violations)

    counts = {
        table: cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "ceremonies", "categories", "nominations", "films", "people",
            "nomination_films", "nomination_people",
        )
    }
    expected = {
        "ceremonies": 98, "categories": 66, "nominations": 12137,
        "films": 5265, "people": 9638, "nomination_films": 10879,
        "nomination_people": 18823,
    }
    check("row counts match data_notes.md scale", counts == expected, counts)

    ceremonies = [r[0] for r in cur.execute("SELECT ceremony FROM ceremonies ORDER BY ceremony")]
    check("ceremonies 1..98 contiguous, no gaps", ceremonies == list(range(1, 99)))

    (n_source,) = cur.execute("SELECT COUNT(DISTINCT source_name) FROM categories").fetchone()
    (n_group,) = cur.execute("SELECT COUNT(DISTINCT award_group) FROM categories").fetchone()
    (n_class,) = cur.execute("SELECT COUNT(DISTINCT class) FROM categories").fetchone()
    check("category hierarchy: 66 source_name / 37 award_group / 8 class",
          (n_source, n_group, n_class) == (66, 37, 8),
          (n_source, n_group, n_class))

    unused = cur.execute("""
        SELECT source_name FROM categories
        WHERE category_id NOT IN (SELECT category_id FROM nominations)
    """).fetchall()
    check("every seeded category matched >=1 nomination", not unused, unused)

    bad_winner = cur.execute(
        "SELECT COUNT(*) FROM nominations WHERE is_winner NOT IN (0, 1)"
    ).fetchone()[0]
    check("is_winner only 0/1", bad_winner == 0)

    empty_noms = cur.execute("""
        SELECT COUNT(*) FROM nominations n
        WHERE n.nomination_id NOT IN (SELECT nomination_id FROM nomination_films)
          AND n.nomination_id NOT IN (SELECT nomination_id FROM nomination_people)
          AND n.citation IS NULL
    """).fetchone()[0]
    check("no nomination with zero film/person/citation", empty_noms == 0)


def aggregate(cur):
    section("aggregate sanity")

    # Filmless nominations: expected in SciTech/Special (department/citation
    # awards, no film credited by design). Outside those two classes, the
    # only filmless rows are 30 discontinued, pre-1933 (ceremony <= 6)
    # categories that recognized a person/department, not a film: assistant
    # director (18), studio sound department (8), engineering effects (2),
    # and title-writing (2) honorable mentions. See data/data_notes.md.
    rows = cur.execute("""
        SELECT c.class, n.raw_category, n.ceremony
        FROM nominations n
        JOIN categories c ON c.category_id = n.category_id
        LEFT JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
        WHERE nf.nomination_id IS NULL AND c.class NOT IN ('SciTech', 'Special')
    """).fetchall()
    expected_raw_categories = {
        "ASSISTANT DIRECTOR", "SOUND RECORDING", "ENGINEERING EFFECTS",
        "WRITING (Title Writing)",
    }
    unexplained = [r for r in rows if r[1] not in expected_raw_categories or r[2] > 6]
    check("30 non-SciTech/Special filmless noms are the known pre-1933 categories",
          len(rows) == 30 and not unexplained, unexplained or len(rows))

    (scitech_special_filmless,) = cur.execute("""
        SELECT COUNT(*) FROM nominations n
        JOIN categories c ON c.category_id = n.category_id
        LEFT JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
        WHERE nf.nomination_id IS NULL AND c.class IN ('SciTech', 'Special')
    """).fetchone()
    check("SciTech/Special filmless count is large (citations, not a gap)",
          scitech_special_filmless > 1000, scitech_special_filmless)

    filmless_acting = cur.execute("""
        SELECT COUNT(*) FROM nominations n
        JOIN categories c ON c.category_id = n.category_id
        LEFT JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
        WHERE nf.nomination_id IS NULL AND c.class = 'Acting'
    """).fetchone()[0]
    check("Acting class has zero filmless nominations", filmless_acting == 0)


def imdb_enrichment(cur):
    section("IMDb enrichment")

    # Coverage: every film with an imdb_id (5,264) matched title.basics on the
    # 2026-07 snapshot; 12 of them have no runtimeMinutes at IMDb. Film 764
    # ("Letter from Livingston") has no imdb_id: release_year 1943 hand-set
    # from the ceremony year, both IMDb columns legitimately NULL.
    coverage = cur.execute("""
        SELECT COUNT(release_year), COUNT(original_title), COUNT(runtime_minutes)
        FROM films
    """).fetchone()
    check("enrichment coverage: 5265 release_year / 5264 original_title / 5252 runtime",
          coverage == (5265, 5264, 5252), coverage)

    no_original = cur.execute(
        "SELECT film_id, imdb_id, release_year FROM films WHERE original_title IS NULL"
    ).fetchall()
    check("only film 764 (no imdb_id, hand-set year 1943) lacks original_title",
          no_original == [(764, None, 1943)], no_original)

    # Values confirmed against the title.basics snapshot by hand.
    spot = cur.execute("""
        SELECT imdb_id, original_title, runtime_minutes FROM films
        WHERE imdb_id IN ('tt6751668', 'tt0028950', 'tt0031381', 'tt0120338')
        ORDER BY imdb_id
    """).fetchall()
    expected = [
        ("tt0028950", "La grande illusion", 113),   # Grand Illusion
        ("tt0031381", "Gone with the Wind", 238),   # original = primary case
        ("tt0120338", "Titanic", 194),              # the 1997 one
        ("tt6751668", "Gisaengchung", 132),         # Parasite
    ]
    check("original_title/runtime spot checks (Parasite, Grand Illusion, GWTW, Titanic)",
          spot == expected, spot)

    # People enrichment (name.basics, 2026-07 snapshot). Companies are absent
    # from name.basics by design: no imdb 'nm' id, no birth/death years.
    people_cov = cur.execute("""
        SELECT kind, COUNT(*), COUNT(imdb_id), COUNT(birth_year), COUNT(death_year)
        FROM people GROUP BY kind ORDER BY kind
    """).fetchall()
    check("people coverage: persons 9337/8588 id/5620 birth/3369 death; companies 301/71/0/0",
          people_cov == [("company", 301, 71, 0, 0), ("person", 9337, 8588, 5620, 3369)],
          people_cov)

    bad_years = cur.execute(
        "SELECT COUNT(*) FROM people WHERE death_year < birth_year"
    ).fetchone()[0]
    check("no death_year before birth_year", bad_years == 0, bad_years)

    people_spot = cur.execute("""
        SELECT imdb_id, name, birth_year, death_year FROM people
        WHERE imdb_id IN ('nm0000031', 'nm4869190', 'nm2353419')
        ORDER BY imdb_id
    """).fetchall()
    expected_people = [
        ("nm0000031", "Katharine Hepburn", 1907, 2003),
        ("nm2353419", "Al Mayer Jr.", 1966, None),   # id swap fix, see CLAUDE.md
        ("nm4869190", "Al Mayer Sr.", 1936, 2018),
    ]
    check("birth/death spot checks (Hepburn, Al Mayer Sr./Jr.)",
          people_spot == expected_people, people_spot)


def spot_checks(cur):
    section("known-fact spot checks")

    def wins_for_imdb(imdb_id):
        return cur.execute("""
            SELECT COUNT(*) FROM films f
            JOIN nomination_films nf ON nf.film_id = f.film_id
            JOIN nominations n ON n.nomination_id = nf.nomination_id
            WHERE f.imdb_id = ? AND n.is_winner = 1
        """, (imdb_id,)).fetchone()[0]

    # Two different films are both titled "Titanic" (1953 tt0046435, 1997
    # tt0120338) -- grouping by title text alone overcounts wins to 12.
    # Match on imdb_id, the reliable identifier, to get the real 11.
    check("Titanic (1997, tt0120338) has 11 wins", wins_for_imdb("tt0120338") == 11,
          wins_for_imdb("tt0120338"))
    check("Ben-Hur (1959, tt0052618) has 11 wins", wins_for_imdb("tt0052618") == 11,
          wins_for_imdb("tt0052618"))

    hepburn_wins = cur.execute("""
        SELECT COUNT(*) FROM people p
        JOIN nomination_people np ON np.person_id = p.person_id
        JOIN nominations n ON n.nomination_id = np.nomination_id
        WHERE p.name = 'Katharine Hepburn' AND n.is_winner = 1
    """).fetchone()[0]
    check("Katharine Hepburn has 4 acting wins", hepburn_wins == 4, hepburn_wins)

    ceremony_1_picture = cur.execute("""
        SELECT f.title FROM nominations n
        JOIN categories c ON c.category_id = n.category_id
        JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
        JOIN films f ON f.film_id = nf.film_id
        WHERE n.ceremony = 1 AND c.award_group LIKE '%Picture%' AND n.is_winner = 1
        ORDER BY f.title
    """).fetchall()
    check("ceremony 1 Best-Picture-type winners include Wings",
          ("Wings",) in ceremony_1_picture, ceremony_1_picture)

    parasite_wins = cur.execute("""
        SELECT c.award_group FROM films f
        JOIN nomination_films nf ON nf.film_id = f.film_id
        JOIN nominations n ON n.nomination_id = nf.nomination_id
        JOIN categories c ON c.category_id = n.category_id
        WHERE f.title = 'Parasite' AND n.is_winner = 1
    """).fetchall()
    parasite_groups = {g for (g,) in parasite_wins}
    check("Parasite (2019) swept Picture/Directing/Writing/Intl Feature",
          parasite_groups == {"Best Picture", "Directing", "Writing", "International Feature Film"},
          parasite_groups)


def round_trip(cur, sample_stride=1000):
    section(f"TSV round-trip sample (every {sample_stride}th row)")

    with open(TSV_PATH) as f:
        columns = f.readline().strip("\n").split("\t")
        lines = f.readlines()

    # ingest.py inserts one nomination per TSV line in file order with an
    # autoincrement PK, so line i (0-indexed, after the header) maps exactly
    # to nomination_id i + 1 -- a reliable join key without re-deriving one.
    for i in range(0, len(lines), sample_stride):
        row = parse_row(lines[i], columns)
        nomination_id = i + 1

        db_row = cur.execute("""
            SELECT raw_category, official_name, is_winner, detail, note, citation
            FROM nominations WHERE nomination_id = ?
        """, (nomination_id,)).fetchone()

        expected = (
            row["Category"], to_null(row["Name"]), parse_winner(row["Winner"]),
            to_null(row["Detail"]), to_null(row["Note"]), to_null(row["Citation"]),
        )
        check(f"line {i + 2}: nomination fields round-trip", db_row == expected,
              (db_row, expected))

        # film_id linkage (count), not title text: enrichment now legitimately
        # rewrites some titles to match IMDb's primaryTitle (see
        # data/title_review_*.txt / CLAUDE.md), so exact text fidelity to the
        # TSV is no longer the invariant post-enrichment -- only linkage is.
        film_names = split_pipe(row["Film"])
        if film_names:
            (linked_count,) = cur.execute("""
                SELECT COUNT(*) FROM nomination_films WHERE nomination_id = ?
            """, (nomination_id,)).fetchone()
            check(f"line {i + 2}: film count round-trip", linked_count == len(film_names),
                  (linked_count, len(film_names)))


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    structural(cur)
    aggregate(cur)
    imdb_enrichment(cur)
    spot_checks(cur)
    round_trip(cur)

    conn.close()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for name in failures:
            print(f"  - {name}")
        sys.exit(1)
    else:
        print("all checks passed")


if __name__ == "__main__":
    main()
