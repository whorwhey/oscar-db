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

What's inside: ceremonies, categories, films, people, and nominations,
with junction tables for the many-to-many relationships (a nomination
can span multiple films/people). Categories are curated dimension data
(66 rows, seeded from `data/categories_seed.tsv`) with a four-level
hierarchy from per-year names up to 8 coarse classes. See `schema.md`
for schema rationale and `data/data_notes.md` for the source data
dictionary.

Current data quality: all 5,265 films have `release_year`; all but one
(an obscure 1943 army short) have an `imdb_id`; film titles match
IMDb's primaryTitle, with divergences reviewed by hand.

### To be updated

- Enrichment: originalTitle + runtimeMinutes (IMDb), Chinese titles/names
  (title_zh, name_zh), douban_id, countries, film_directors
- Query interfaces, built as learning demos: canned queries, small CLI,
  text-to-SQL LLM demo
- Rebuild/merge tooling for reapplying enrichment after a schema change

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

Corrections and enrichment (`release_year`, film titles) come from
[IMDb's non-commercial datasets](https://datasets.imdbws.com/)
(`title.basics.tsv.gz`), joined on `imdb_id`. Snapshot downloaded
2026-07-07; the file is refreshed daily by IMDb and is not committed to
this repo, so a fresh download may differ slightly from what the
enrichment was run against.

## License

Code is MIT-licensed (see `LICENSE`). `data/oscars.tsv` and the
resulting `data/oscars.db` are derived from `DLu/oscar_data`, licensed
BSD 2-Clause by its author — see the upstream repo for the full license
text. IMDb-derived fields are from IMDb's non-commercial datasets,
subject to [their terms](https://developer.imdb.com/non-commercial-datasets/).
