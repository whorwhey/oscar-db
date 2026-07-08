# Data Notes (Sources & Data Dictionary)

The database draws on two sources with distinct authority boundaries:

1. **DLu's TSV** (`data/oscars.tsv`): which ceremonies/nominations/films/
   people exist and how they connect. Bootstrap-only.
2. **IMDb non-commercial datasets** (`data/title.basics.tsv.gz`): film
   titles, original titles, release years, runtimes. Re-runnable sync.

Categories are not sourced at all — we author them (see "Categories:
curated by us" below).

Working rules and the authority summary live in CLAUDE.md; schema rationale
in schema.md. This file is the deeper reference on each source.

## Source 1: DLu's TSV (bootstrap)

`DLu/oscar_data` on GitHub (BSD 2-Clause). Community dataset parsed from the
official Academy site (awardsdatabase.oscars.org) with IMDb IDs merged in.
Not official; spot-check against the official site when in doubt.

Bootstrap-only: ingested once by `src/ingest.py`, never routinely reloaded —
`data/oscars.db` is the maintained artifact, and reloading would destroy
enrichment (ingest.py refuses to run on an enriched db without --force).

### File quirks (`data/oscars.tsv`)

- **Tab-separated** despite the original `.csv` name.
- 12,138 lines = 1 header + 12,137 nominations. One row = one nomination.
- Multi-valued cells are **pipe-separated** (`|`). `Film`/`FilmId` and
  `Nominees`/`NomineeIds` are exploded via junction tables (`nomination_films`,
  `nomination_people`). `Detail`/`Note`/`Citation` are NOT exploded — they stay
  as single verbatim TEXT columns on `nominations`, pipes and all, since
  schema.sql has no per-film/per-person junction for them.
- Unknown IMDb IDs appear as `?` → convert to NULL on ingestion.
- `Winner` is `True` or empty → store as INTEGER 0/1 (SQLite has no BOOLEAN).

### Column semantics

- **Ceremony**: ordinal integer (1–98). 1st ceremony (held 1929) honored films
  of 1927/28.
- **Year**: ceremony's honored-year label (e.g. "1927/28"). NOT necessarily a
  film's release year; `films.release_year` comes from IMDb.
- **Category vs CanonicalCategory**: raw = name as written that year
  (e.g. `ACTOR`, 1st ceremony); CanonicalCategory = spelling variants merged
  across years, but NOT modernized — historical names survive (SOUND
  RECORDING, SCIENTIFIC OR TECHNICAL AWARD (Class I)). 66 distinct values.
  Stored as `categories.source_name`; it is the join key into our curated
  categories table. Query on `award_group` (or `class`) for grouping; keep
  raw_category for fidelity.
- **Class (dataset column)**: IGNORED at ingestion. We curate our own class
  in the seed file (the dataset's grouping dropped the official facets and
  invented ones we don't need, e.g. "Title").
- **Name vs Nominees**: Name = official display text as written; Nominees =
  cleaned, structured list of entities. Store Name on the nomination; explode
  Nominees into the `people` table.
- **Detail**: short, category-dependent info (character name for acting, song
  title for Best Song).
- **Note**: free-prose footnotes.
- **Citation**: official award-statement text; used for Honorary and
  Scientific/Technical awards (often no film attached). Empty otherwise.
- **Companies as nominees**: some nominee IDs are IMDb company IDs (`co...`
  vs `nm...` for persons), e.g. Best Picture went to studios early on
  (Wings → Paramount Famous Lasky), and Sci-Tech awards go to firms.
  `people.kind` is derived from the ID prefix.
- **Film titles in the TSV are no longer authoritative**: `films.title` was
  synced to IMDb's primaryTitle (2026-07-07). verify.py's round-trip
  therefore checks film *linkage* counts, not title text.

## Source 2: IMDb title.basics (enrichment)

`title.basics.tsv.gz` from datasets.imdbws.com (IMDb non-commercial
datasets). ~213MB, gitignored, re-downloadable; current snapshot 2026-07.
One row per title; missing values are the literal sentinel `\N`.

Fields we use, joined on `tconst` = `films.imdb_id`:

- **primaryTitle** → `films.title` (one-off sync 2026-07-07; since then
  `src/enrich_imdb.py` only *reports* divergence, currently 0 under
  casefolded/whitespace-normalized comparison).
- **originalTitle** → `films.original_title`, stored verbatim for every
  matched film, even when identical to `title` (~88% of films) — so NULL
  cleanly means unknown, and no COALESCE fallback is needed (unlike
  `title_zh`).
- **startYear** → `films.release_year`.
- **runtimeMinutes** → `films.runtime_minutes`.

Sync semantics (`src/enrich_imdb.py`): keyed on imdb_id (never the surrogate
film_id, per CLAUDE.md); re-runnable/idempotent; an IMDb `\N` never
overwrites a value already in the db (protects hand-entered fixes).

Foreign-language originals: `WHERE original_title <> title` — but note it
matches 716 films, not the 625 whose originalTitle differs from
primaryTitle at IMDb. The extra ~91 are titles differing from primaryTitle
only in case/whitespace (the title sync compared casefolded, and SQLite's
`<>` is case-sensitive), e.g. "À Nous la Liberté" vs IMDb's
"À nous la liberté".

Coverage: all 5,264 films with an imdb_id match a title.basics row; 12 have
no runtimeMinutes at IMDb. Film 764 ("Letter from Livingston") has no
imdb_id at all — release_year 1943 hand-set, IMDb columns NULL.

Hand fixes: individual corrections where neither source is right (stale
imdb_id, missing release_year, …) — the running list is "Resolved data
quirks" in CLAUDE.md.

## Categories: curated by us

`data/categories_seed.tsv`: facts (nominations, films, people: thousands
of rows) are parsed from the dataset — it is the authority. Dimensions
(categories: 66 rows we make editorial decisions about) are curated seed
data — we are the authority. Ingestion therefore VALIDATES categories
rather than creating them: an unknown CanonicalCategory crashes the run
(KeyError) so a human classifies it. Trade-off accepted: the seed is
coupled to DLu's exact spellings, and an upstream rename breaks ingestion
loudly — which beats silent misclassification. Hierarchy: raw_category →
source_name (66) → award_group (37, official-site facets) → class (8).
Judgment calls in the mapping are documented in schema.md.

## Design decisions (schema-level)

- **Surrogate integer primary keys** everywhere; `imdb_id` is nullable-but-unique
  (can be unknown, so it can't be the PK). Enrichment is still always keyed
  on imdb_id — surrogate ids are stable only by accident of insertion order.
- **NULL means unknown/absent.** No sentinel values. Display fallback
  (e.g. show English title when no Chinese one exists) is query-time logic:
  `COALESCE(title_zh, title)` — never stored.
- `title_zh` / `name_zh` hold Simplified Chinese (zh-Hans). NULL until filled
  (manual or Douban enrichment).
- `douban_id` NULL for now; Douban has no official API — future scraping lesson.
  Some films will never have one (too obscure, or censored).
- **Countries are junctions** (`film_countries`, `person_countries`), not
  columns: co-productions and dual citizenship are common. Empty until
  enrichment. For people, "nationality" is messy — IMDb gives birthplace, not
  citizenship; Wikidata is the better future source.
- International Feature quirk: for that category the official "nominee" is
  historically the country itself (e.g. Parasite → South Korea), so some
  country data is extractable from nominee fields before full enrichment.
- Directors are NOT a column on films: co-directors exist, and this dataset
  only knows directors via Directing-category nominations. Derive by query for
  now; add a `film_directors` junction during IMDb enrichment.

## Scale (actual)

ceremonies 98 · categories 66 (seeded) · nominations 12,137 · films 5,265 ·
people 9,663 · nomination_films 10,879 · nomination_people 18,823.
Enrichment coverage on films: imdb_id 5,264 · release_year 5,265 ·
original_title 5,264 · runtime_minutes 5,252.
Total ~57k rows, a few MB — trivial for SQLite.
