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

## Status & roadmap (2026-07-07)

Done: schema, ingestion, category seed, verification queries, initial
commit (695d70d). Not pushed — README and db quality confirmation first.

Next, in order:
1. Correctness test script (src/verify.py, `uv run`): structural checks,
   known-fact spot checks, aggregate sanity, TSV round-trip sample.
   Also explain the 30 filmless Directing/Production/Writing nominations.
2. Decide rebuild-safety for enrichment (likely: enrichment lives in
   seed files like categories_seed.tsv; db stays a pure build artifact).
   Blocks all enrichment work.
3. Interface demos: canned queries, small CLI, text-to-SQL LLM demo.
   GUI = VS Code SQLite Viewer extension.
4. Enrichment: title_zh/name_zh, release_year (IMDb), douban_id,
   countries, film_directors junction (schema discussion needed).
5. README, then push.
