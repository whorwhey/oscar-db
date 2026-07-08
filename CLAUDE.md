# oscar-db

Curated SQLite Oscar-nominations database. Bootstrapped once from a
community scrape (`data/oscars.tsv`, DLu/oscar_data), now corrected and
enriched in place against IMDb's datasets; `data/oscars.db` is the
maintained, git-tracked artifact. Repo: github.com/whorwhey/oscar-db.

I'm learning SQL/databases — explain reasoning, go step by step, let me
attempt things first. Before nontrivial edits, tell me the plan first.

Design docs: schema.md (schema rationale), data/data_notes.md (source
data dictionary). Read both before schema or data work.

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
- IMDb non-commercial datasets (title.basics.tsv.gz, gitignored,
  re-downloadable from datasets.imdbws.com): authority for film titles
  (primaryTitle) and release_year. Joined on imdb_id.
- Us: categories seed (66 rows, data/categories_seed.tsv), hand fixes
  for cases neither source gets right (see "Resolved data quirks").
- All enrichment/corrections keyed on imdb_id (external, stable) — NOT
  the surrogate integer ids, which are stable only by accident of
  insertion order. If a rebuild is ever needed, enrichment must be
  reapplied by imdb_id; no merge script exists yet (build when needed).

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
- src/enrich_release_year.py: re-runnable IMDb sync; also reports (not
  writes) title mismatches against primaryTitle. Currently 0 mismatches.

## Resolved data quirks (reference, all handled)

- film_id 764 "Letter from Livingston": only film with no imdb_id
  (obscure 1943 army short, absent from DLu's IMDb matching);
  release_year 1943 set by hand from ceremony year.
- film_id 5030 Summer of Soul: DLu had stale imdb_id tt11422728
  (retired/merged on IMDb's side); hand-corrected to tt7378922.
- film_id 1826: was mistitled "A Place in the Sun" — actually a 1960
  Czech animated short ("O místo na slunci"), not the 1951 Stevens
  film; fixed via primaryTitle sync.
- 422 title divergences from primaryTitle reviewed in three batches
  (formatting; creator-possessives like "Bram Stoker's Dracula";
  alternate/reissue titles) — all synced to IMDb by decision 2026-07-07.
- 30 filmless Directing/Production/Writing nominations are pre-1933
  discontinued categories crediting a person/department, not a film.
  SciTech/Special filmless nominations (994 + 256) are citation-based
  awards, expected by design.
- Title text is not unique: two films named "Titanic" (1953 tt0046435,
  1997 tt0120338). Any title-lookup interface must disambiguate/ask,
  never silently pick or merge.

## Roadmap

1. Commit current state (title sync + docs), push.
2. IMDb follow-ups: originalTitle (restores original-language titles
   dropped by the primaryTitle sync — recoverable anytime via imdb_id)
   and runtimeMinutes. Needs schema discussion (new columns).
3. Interface demos: canned queries, small CLI, text-to-SQL LLM demo.
   GUI = VS Code SQLite Viewer extension. Respect the Titanic
   disambiguation rule above.
4. Remaining enrichment: title_zh/name_zh, douban_id, countries,
   film_directors junction (schema discussion needed).
