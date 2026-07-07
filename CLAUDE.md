# oscar-db

Learning project: SQLite Oscar database built from a community-parsed
scrape of the Academy Awards site (`data/oscars.tsv`). I'm new to SQL/
databases — explain reasoning, go step by step, let me attempt things
first.

Design docs: schema.md (schema rationale), data/data_notes.md (source
data dictionary). Read both before schema or data work.

## Schema

schema.sql is settled — don't change without discussing. Core design:
fact tables (nominations, films, people — parsed from the source, which
is the authority) vs. dimension data (categories — 66 rows we make
editorial calls about, seeded from data/categories_seed.tsv).

Category hierarchy, finest to coarsest:
```
raw_category (per-year text) → source_name (66, DLu's CanonicalCategory)
  → award_group (37, official-site facets) → class (8 coarse groups)
```

## Ingestion (src/ingest.py)

- Self-contained and destructive: every run deletes `data/oscars.db`,
  re-applies schema.sql, and re-ingests from `data/oscars.tsv`. The db is
  a pure build artifact, not persisted state.
- Must run `PRAGMA foreign_keys = ON` per connection.
- Categories are validated, not discovered: an unknown CanonicalCategory
  in the source data, or an unused seed row, crashes the run by design.
- Smoke test: run ingestion twice back-to-back; row counts must match
  both times.

## Env

uv on macOS. Always `uv run ...` — never bare `python`.

## Before the enrichment phase

The rebuild-on-every-run design is only safe while the db holds nothing
non-regenerable. Once enrichment adds hand-entered data (`title_zh`,
etc.), this must be revisited — a destructive rebuild would wipe it.
