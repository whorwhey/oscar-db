# oscar-db

A curated SQLite database of Academy Awards (Oscars) nominations and
winners, 1st ceremony (1927/28) through the 98th (2025). Bootstrapped
from a community-parsed scrape of the official Academy site, then
corrected and enriched against IMDb's datasets. A personal project for
learning SQL, database design, and data curation — shared in case it's
useful to others.

## Description

The database itself (`data/oscars.db`) is the maintained artifact — not
a build script's output. It was generated once from the source TSV and
is since edited in place: titles corrected, stale IMDb IDs fixed,
release years added. Rows are cross-referenced to IMDb by `imdb_id`.

Current data quality: all 5,265 films have `release_year`; all but one
(an obscure 1943 army short) have an `imdb_id` and `original_title`;
99.8% have `runtime_minutes` (the rest are missing at IMDb); film
titles match IMDb's primaryTitle, with divergences reviewed by hand.
Of the 10,838 persons, 93% have an `imdb_id` (the rest — mostly early
Sci-Tech honorees — have no IMDb record); names match IMDb's
primaryName; 6,785 have `birth_year` and 4,087 `death_year`, the
remainder missing at IMDb. 1,508 of these persons are directors who
were never personally nominated, added via `film_directors` (all
matched to IMDb).

### Database structure

Five entity tables plus junctions (full DDL in `schema.sql`, rationale
in `schema.md`, per-source details in `data/data_notes.md`):

- **`ceremonies`** (98) — ceremony ordinal and honored-year label
  (`"1927/28"`). The label is the *honored* year, not the event year.
- **`categories`** (66, curated, seeded from
  `data/categories_seed.tsv`) — one row per historical category
  name, with a hierarchy for grouping: `source_name` (66, e.g. `SOUND
  RECORDING`) → `award_group` (37, the official site's facets, e.g.
  Sound Mixing) → `class` (8 coarse groups, e.g. Music). Query on
  `award_group` or `class`; use `nominations.raw_category` for the
  name as written that year.
- **`films`** (5,265) — `title` (follows IMDb's primaryTitle),
  `original_title` (IMDb's originalTitle, verbatim), `release_year`,
  `runtime_minutes`, `imdb_id`; `title_zh` and `douban_id` are
  reserved for planned enrichment.
- **`people`** (11,144 = 10,838 persons + 306 companies) — nominees,
  plus directors linked via `film_directors` who were never nominated
  themselves; `kind` distinguishes persons from companies and other
  organizations (early Best Picture went to studios; Sci-Tech awards go
  to firms; wartime documentaries credited government agencies). `name`
  follows IMDb's primaryName; `birth_year`/`death_year` from IMDb
  (`NULL` death year means unknown *or* still alive). `name_zh` and
  `douban_id` reserved.
- **`nominations`** (12,137) — one row per nomination, with
  `is_winner`, category links, and verbatim `detail`/`note`/`citation`
  text. Honorary and Sci-Tech awards are citation-based and often link
  to no film — that's by design, not missing data.
- **Junctions** — `nomination_films` and `nomination_people` (a
  nomination can span several films/people and vice versa);
  `film_directors` (5,189 films → 3,213 directors, from IMDb crew data,
  independent of nomination history); `film_countries`/`person_countries`
  exist but are empty pending enrichment.

Conventions: `NULL` always means unknown/absent — there are no
sentinel values. `imdb_id` is the stable external key (`tt...` films,
`nm...`/`co...` people); the integer primary keys are surrogates.
Film titles are **not** unique — two different films are named
"Titanic" (1953 and 1997) — so group and join by `film_id` or
`imdb_id`, never by title text:

```sql
-- Most-awarded films. GROUP BY film_id, not title: two films
-- are named "Titanic", and grouping by title would merge them.
SELECT f.title, f.release_year, COUNT(*) AS wins
FROM films f
JOIN nomination_films nf USING (film_id)
JOIN nominations n USING (nomination_id)
WHERE n.is_winner = 1
GROUP BY f.film_id
ORDER BY wins DESC
LIMIT 5;
```

### To be updated

- Enrichment: Chinese titles/names (title_zh, name_zh), douban_id,
  countries
- Query interfaces, built as learning demos: canned queries, small CLI,
  text-to-SQL LLM demo

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python >= 3.13.

```sh
git clone https://github.com/whorwhey/oscar-db.git
cd oscar-db
uv sync
```

## Usage

TBD — no query interface yet. In the meantime:

- `uv run src/verify.py` runs correctness checks against `data/oscars.db`.
- Browse the db directly with any SQLite client (e.g. the VS Code
  SQLite Viewer extension).

## Contributing

Personal project, not currently accepting external contributions. Open
an issue if you spot a data or schema problem.

### Data sources

Initial data from [`DLu/oscar_data`](https://github.com/DLu/oscar_data)
on GitHub (BSD 2-Clause), a community-maintained scrape of
awardsdatabase.oscars.org with IMDb IDs merged in. Not an official
Academy dataset. See `data/data_notes.md` for source quirks and column
semantics. Snapshot downloaded 2026-07-05 (covers through the 98th
ceremony, 2025).

Corrections and enrichment (film titles, `original_title`,
`release_year`, `runtime_minutes`; people names, `birth_year`,
`death_year`; `film_directors` links) come from
[IMDb's non-commercial datasets](https://datasets.imdbws.com/)
(`title.basics.tsv.gz`, `name.basics.tsv.gz`, `title.crew.tsv.gz`),
joined on `imdb_id`. Snapshots downloaded 2026-07-07/09; the files are
refreshed daily by IMDb and are not committed to this repo, so a fresh
download may differ slightly from what the enrichment was run against.

## License

Code is MIT-licensed (see `LICENSE`). `data/oscars.tsv` and the
resulting `data/oscars.db` are derived from `DLu/oscar_data`, licensed
BSD 2-Clause by its author — see the upstream repo for the full license
text. IMDb-derived fields are from IMDb's non-commercial datasets,
subject to [their terms](https://developer.imdb.com/non-commercial-datasets/).
