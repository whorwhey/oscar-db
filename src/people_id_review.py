# Regenerates data/people_no_imdb_id.txt: persons (kind='person') with no
# imdb_id, ranked for hand review. Report-only; never writes to the db.
# Groups: 1. exact-name candidates in name.basics (with dup annotations)
#         2. ambiguous name matches   3. no match   4. company-looking
# Group 2 rows are all filmless Sci-Tech/Special citations, so candidates
# are narrowed by profession + birth/death plausibility (not film overlap)
# and sorted easiest-first by narrowed_count.
# Hand-fix history lives in CLAUDE.md ("Resolved data quirks").

import gzip
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from enrich_imdb import normalize

DB_PATH = "data/oscars.db"
NAMES_PATH = "data/name.basics.tsv.gz"
OUT_PATH = "data/people_no_imdb_id.txt"

COMPANY_RE = re.compile(
    r"INC\.?|CORP|COMPANY|COMPANIES|LTD|LLC|DEPARTMENT|DEPT|STUDIO|LABORATOR"
    r"|PRODUCTS|PRODUCTIONS|DIVISION|SYSTEMS|ELECTRIC|MANUFACTUR|PHOTOPHONE"
    r"|OPTICAL|CAMERA|RESEARCH|INDUSTR|ASSOCIATES|TECHNOLOG|ENGINEERING|BROS",
    re.IGNORECASE)

# Every ambiguous-group nomination is a Sci-Tech/Special citation award
# (verified 2026-07-10: none of them link to a film), so a plausible
# candidate should carry a technical-crew profession, not e.g. 'actor'.
TECH_PROFESSIONS = {
    "camera_department", "sound_department", "editorial_department", "editor",
    "cinematographer", "special_effects", "visual_effects", "art_department",
    "electrical_department", "animation_department", "miscellaneous",
    "production_manager", "art_director", "production_designer", "composer",
    "music_department", "costume_department", "make_up_department",
    "transportation_department", "production_department", "location_management",
}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    rows = cur.execute(
        "SELECT person_id, name FROM people"
        " WHERE imdb_id IS NULL AND kind = 'person' ORDER BY person_id"
    ).fetchall()
    wanted = {}
    for person_id, name in rows:
        wanted.setdefault(normalize(name), []).append((person_id, name))

    our_films = {r[0] for r in cur.execute(
        "SELECT imdb_id FROM films WHERE imdb_id IS NOT NULL")}

    # earliest nomination year per person, for birth/death plausibility
    nom_year = {}
    for person_id, year_label in cur.execute("""
        SELECT np.person_id, MIN(ce.year_label) FROM nomination_people np
        JOIN nominations n ON n.nomination_id = np.nomination_id
        JOIN ceremonies ce ON ce.ceremony = n.ceremony
        GROUP BY np.person_id
    """).fetchall():
        nom_year[person_id] = int(year_label[:4])

    candidates = {}
    with gzip.open(NAMES_PATH, "rt", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        idx = {name: i for i, name in enumerate(header)}
        for line in f:
            fields = line.rstrip("\n").split("\t")
            key = normalize(fields[idx["primaryName"]])
            if key not in wanted:
                continue
            kft = fields[idx["knownForTitles"]]
            known = set() if kft == r"\N" else set(kft.split(","))
            by = fields[idx["birthYear"]]
            dy = fields[idx["deathYear"]]
            prof = fields[idx["primaryProfession"]]
            candidates.setdefault(key, []).append((
                fields[idx["nconst"]], known,
                None if by == r"\N" else int(by),
                None if dy == r"\N" else int(dy),
                set() if prof == r"\N" else set(prof.split(",")),
            ))

    def fmt_cand(c):
        nconst, _known, by, dy, prof = c
        return f"{nconst}({by or '?'}-{dy or ''},{'|'.join(sorted(prof)) or '?'})"

    def narrow(cands, year):
        # Every ambiguous row is a filmless Sci-Tech/Special citation (verified
        # 2026-07-10), so knownForTitles overlap can't help; instead keep only
        # candidates whose profession/lifespan are plausible for that award.
        out = []
        for c in cands:
            _nconst, _known, by, dy, prof = c
            if year is not None and by is not None and by > year - 12:
                continue
            if year is not None and dy is not None and dy < year:
                continue
            if prof and not (prof & TECH_PROFESSIONS):
                continue
            out.append(c)
        return out

    grouped = {1: [], 2: [], 3: [], 4: []}
    for key, persons in wanted.items():
        cands = candidates.get(key, [])
        overlapping = [c for c in cands if c[1] & our_films]
        if len(cands) == 1:
            chosen = cands[0][0]
            basis = "unique+film" if overlapping else "unique"
        elif len(overlapping) == 1:
            chosen, basis = overlapping[0][0], f"film-of-{len(cands)}"
        elif cands:
            chosen, basis = "", f"ambiguous:{len(cands)}"
        else:
            chosen, basis = "", ""

        for person_id, name in persons:
            if chosen:
                holder = cur.execute(
                    "SELECT person_id, name FROM people WHERE imdb_id = ?", (chosen,)
                ).fetchone()
                if holder:
                    basis_out = f"{basis}; DUP: id already on person {holder[0]} {holder[1]!r} -- merge?"
                elif len(persons) > 1:
                    twins = [p for p, _ in persons if p != person_id]
                    basis_out = f"{basis}; DUP-PAIR with person {twins} -- merge?"
                else:
                    basis_out = basis
                grouped[1].append((person_id, name, chosen, basis_out, "", ""))
            elif basis:
                narrowed = narrow(cands, nom_year.get(person_id))
                shown = narrowed if narrowed else cands  # fall back if over-filtered
                fallback = "" if narrowed else " (narrowed to 0, showing all)"
                grouped[2].append((
                    person_id, name, "", f"{basis}{fallback}",
                    len(narrowed), "; ".join(fmt_cand(c) for c in shown),
                ))
            elif COMPANY_RE.search(name):
                grouped[4].append((person_id, name, "", "company-looking (kind still 'person')", "", ""))
            else:
                grouped[3].append((person_id, name, "", "", "", ""))

    conn.close()

    titles = {1: "name-match candidates", 2: "ambiguous name matches",
              3: "no match", 4: "no match, company-looking"}

    def sort_key(group, row):
        if group == 2:
            narrowed_count = row[4]
            return (narrowed_count if narrowed_count > 0 else 999, row[0])
        return (row[0],)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("person_id\tname\timdb_id_candidate\tmatch_basis\tnarrowed_count\tcandidates\n")
        for group in (1, 2, 3, 4):
            f.write(f"# --- {titles[group]}: {len(grouped[group])} ---\n")
            for row in sorted(grouped[group], key=lambda r: sort_key(group, r)):
                f.write("\t".join(str(v) for v in row) + "\n")

    for group in (1, 2, 3, 4):
        print(f"{titles[group]}: {len(grouped[group])}")
    print(f"total: {sum(len(v) for v in grouped.values())} -> {OUT_PATH}")


if __name__ == "__main__":
    main()
