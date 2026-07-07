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

- Self-contained and destructive: deletes `data/oscars.db`, re-applies
  schema.sql, and re-ingests from `data/oscars.tsv`.
- Rare/manual now, not routine: `data/oscars.db` is persisted state
  (git-tracked), not a disposable build artifact, once enrichment data
  lives in it. Rerun only to bootstrap from scratch or after a real
  schema/source change — never casually. Guarded: refuses to run if the
  existing db already has non-null enrichment data, to stop an
  accidental wipe of hand-entered work (see decision below).
- Must run `PRAGMA foreign_keys = ON` per connection.
- Categories are validated, not discovered: an unknown CanonicalCategory
  in the source data, or an unused seed row, crashes the run by design.
- Smoke test (only meaningful pre-enrichment, or on a scratch copy): run
  ingestion twice back-to-back; row counts must match both times.

## Env

uv on macOS. Always `uv run ...` — never bare `python`.

## Enrichment persistence (decided 2026-07-07)

`data/oscars.tsv` was only ever needed to originally generate
`data/oscars.db`; historical Oscar data essentially never changes, so
reloading it is not routine. Decision: `oscars.db` becomes the persisted
source of truth going forward, hand-enrichment (`title_zh`, `release_year`,
etc.) is edited directly in it, and the db is git-tracked (no longer
gitignored).

Consequence: ingest.py is no longer safe to rerun blindly (see guard
above). If a real rebuild is ever needed (schema change, corrected
source data), enrichment columns must be reapplied afterward keyed on
`imdb_id` (external, stable) — NOT the surrogate integer id, which is
only stable by accident of deterministic insertion order, not by
contract. No merge script exists yet; build one when a rebuild is
actually needed.

## Status & roadmap (2026-07-07)

Done: schema, ingestion, category seed, verification queries, initial
commit (695d70d), correctness test script (src/verify.py — all checks
pass). Not pushed — README first.

The 30 filmless Directing/Production/Writing nominations are explained:
all pre-1933 (ceremony <= 6), discontinued categories that credited a
person/department, not a film — ASSISTANT DIRECTOR (18), SOUND RECORDING
studio-department awards (8), ENGINEERING EFFECTS (2), WRITING (Title
Writing) (2). SciTech/Special filmless nominations (994 + 256) are
separately expected — citation-based awards by design.

Next, in order:
1. Finish rebuild-safety for enrichment: guard in ingest.py against
   wiping non-null enrichment data (see "Enrichment persistence" above).
2. README, then push.
3. Enrichment: release_year (IMDb) first — simplest field, one value per
   film, no schema discussion needed.
4. Interface demos: canned queries, small CLI, text-to-SQL LLM demo.
   GUI = VS Code SQLite Viewer extension. Design note: title text is not
   unique (e.g. two films named "Titanic", 1953 tt0046435 and 1997
   tt0120338 — found via verify.py spot check); a title-only query
   interface should disambiguate/ask, not silently pick or merge matches.
5. Remaining enrichment: title_zh/name_zh, douban_id, countries,
   film_directors junction (schema discussion needed).
