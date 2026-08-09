# oscar-db

Curated SQLite Oscar-nominations database. Bootstrapped once from a
community scrape (`data/oscars.tsv`, DLu/oscar_data), now corrected and
enriched in place against IMDb's datasets; `oscars.db` (repo root) is
the maintained, git-tracked artifact. Repo: github.com/whorwhey/oscar-db.

I'm learning SQL/databases — explain reasoning, go step by step, let me
attempt things first. Before nontrivial edits, tell me the plan first.

Design docs: schema.md (schema rationale), data/data_notes.md (source
data dictionary). Read both before schema or data work. Full project
history (roadmap log + resolved data quirks): docs/project_history.md.

## Scope (agreed 2026-07-07)

- Personal learning project, but README/repo kept complete enough for a
  stranger to clone and query.
- The db is the product; interfaces (canned queries, small CLI,
  text-to-SQL LLM demo) are learning demos on top, not products.
- Chinese-language layer (title_zh/name_zh, douban_id) is one planned
  enrichment among several, not a headline goal.

## Data authority

- DLu's TSV: authority for which ceremonies/nominations/films/people
  exist and how they connect. Bootstrap-only; never routinely reloaded.
- IMDb non-commercial datasets (title.basics.tsv.gz, name.basics.tsv.gz,
  title.crew.tsv.gz; gitignored, re-downloadable from
  datasets.imdbws.com): authority for film titles (primaryTitle),
  original_title, release_year, runtime_minutes; people names
  (primaryName), birth_year, death_year; film_directors links.
  Joined on imdb_id.
- Us: categories seed (66 rows, data/categories_seed.tsv), hand fixes
  for cases neither source gets right (see docs/project_history.md's
  "Resolved data quirks").
- All enrichment/corrections keyed on imdb_id (external, stable) — NOT
  the surrogate integer ids, which are stable only by accident of
  insertion order. The db itself is the durable artifact going forward;
  no rebuild-from-TSV path is planned (agreed 2026-07-09).

## Schema

schema.sql is settled — don't change without discussing. Fact tables
(nominations, films, people) vs. curated dimension data (categories).
films.title now follows IMDb primaryTitle, not DLu's spelling.

Category hierarchy, finest to coarsest:
```
raw_category (per-year text) → source_name (66, DLu's CanonicalCategory)
  → award_group (37, official-site facets) → class (8 coarse groups)
```

## Working on the repo

- Env: uv on macOS. Always `uv run ...` — never bare `python`.
- Every sqlite connection: `PRAGMA foreign_keys = ON`.
- After any db change: `uv run src/verify.py` (structural checks,
  aggregate sanity, known-fact spot checks, TSV round-trip sample —
  round-trip checks linkage counts, not title text, since titles are
  legitimately enriched away from the TSV).
- src/ingest.py is bootstrap-only and destructive (drops the db). It
  refuses to run if the db holds non-null enrichment data; --force
  overrides. Never run it casually — the db contains hand-entered work.
- src/enrich_imdb.py: re-runnable IMDb sync — films (release_year,
  original_title, runtime_minutes) and people (birth_year, death_year;
  kind='person' only); never overwrites db values with IMDb NULLs;
  reports (not writes) title/name divergence from primaryTitle/
  primaryName — currently 0 for both.
- src/text_to_sql.py needs `CBORG_API_KEY` (not `ANTHROPIC_API_KEY`) —
  full gateway/model/budget config in docs/text_to_sql.md's "CBORG
  configuration" section; read that before re-deriving it again.

## Roadmap

**Active**

1. Remaining enrichment: name_zh, douban_id (title_zh done — see
   docs/project_history.md).

Full history of completed/dropped roadmap items and the detailed
record of hand-resolved data quirks: docs/project_history.md.
