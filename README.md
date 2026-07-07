# oscar-db

A SQLite database of Academy Awards (Oscars) nominations and winners,
built from a community-parsed scrape of the official Academy site. A
personal learning project for SQL/database fundamentals.

## Description

`oscars.db` models ceremonies, categories, films, people, and
nominations, with junction tables for the many-to-many relationships
(a nomination can span multiple films/people). Categories are curated,
editorial dimension data (66 rows, seeded from
`data/categories_seed.tsv`), separate from the parsed fact tables. See
`schema.md` for full schema rationale and `data/data_notes.md` for the
source data dictionary.

### To be updated

- Enrichment: release_year, title_zh/name_zh, douban_id, countries,
  film_directors
- Query interface: CLI, canned queries, text-to-SQL demo
- Rebuild/merge tooling for reapplying enrichment after a schema change


## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python >= 3.13.

```sh
git clone <this-repo>
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

### Data source

Initial data from [`DLu/oscar_data`](https://github.com/DLu/oscar_data)
on GitHub (BSD 2-Clause), a community-maintained scrape of
awardsdatabase.oscars.org with IMDb IDs merged in. Not an official
Academy dataset — spot-check against the official site when in doubt.
See `data/data_notes.md` for source quirks and column semantics.


## License

Code is MIT-licensed (see `LICENSE`). `data/oscars.tsv` and the
resulting `data/oscars.db` are derived from `DLu/oscar_data`, licensed
BSD 2-Clause by its author — see the upstream repo for the full license
text.


