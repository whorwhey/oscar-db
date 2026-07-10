# Data Notes (Sources & Data Dictionary)

The database draws on two sources with distinct authority boundaries:

1. **DLu's TSV** (`data/oscars.tsv`): which ceremonies/nominations/films/
   people exist and how they connect. Bootstrap-only.
2. **IMDb non-commercial datasets** (`data/title.basics.tsv.gz`,
   `data/name.basics.tsv.gz`, `data/title.crew.tsv.gz`): film titles,
   original titles, release years, runtimes; people names, birth/death
   years; film-director links. Re-runnable sync.

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
  `people.kind` is derived from the ID prefix; ID-less nominees defaulted
  to 'person', and 230 of those were organizations — reclassified to
  'company' by award-context review 2026-07-09, so kind is no longer
  purely prefix-derived.
- **Duplicate person rows**: DLu lacks IMDb IDs for many recent SciTech
  honorees, so the same engineer could enter once with an ID and once
  without (ingest dedupes ID-less nominees by name only among themselves,
  case-sensitively, and never across the ID boundary — deliberately, to
  avoid fusing real namesakes). 25 such duplicates were verified by award
  context and merged 2026-07-09.
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

## Source 3: IMDb name.basics (enrichment)

`name.basics.tsv.gz` from datasets.imdbws.com, ~292MB, gitignored,
re-downloadable; current snapshot 2026-07. One row per name record
(`nconst`); `\N` sentinel as in title.basics.

Fields we use, joined on `nconst` = `people.imdb_id`, `kind = 'person'`
only (companies carry `co...` IDs and are absent from name.basics by
design):

- **primaryName** → `people.name` (one-off sync 2026-07-09, same decision
  as film titles; since then `src/enrich_imdb.py` only reports divergence,
  currently 0). The Academy's display text is not lost — it stays verbatim
  on `nominations.official_name`.
- **birthYear** → `people.birth_year`.
- **deathYear** → `people.death_year`. NULL is ambiguous by design: IMDb
  has `\N` both for the living and for unknown deaths.

Sync semantics: identical to title.basics (keyed on imdb_id, re-runnable,
an IMDb `\N` never overwrites a db value).

Coverage: 8,588 of 9,337 persons have an imdb_id, every one matching a
name.basics row; 5,620 have birth_year, 3,369 death_year. The 749 ID-less
persons — mostly pre-1960s SciTech honorees with no IMDb record — are
ranked for review in `data/people_no_imdb_id.txt` (regenerate:
`uv run src/people_id_review.py`; ~180 IDs were recovered 2026-07-09 by
exact-name matching verified against knownForTitles, and are now regular
enriched rows).

## Source 4: IMDb title.crew (enrichment)

`title.crew.tsv.gz` from datasets.imdbws.com, ~78MB, gitignored,
re-downloadable; current snapshot 2026-07. One row per title (`tconst`);
`directors` is a comma-separated list of `nconst`s (IMDb's listing order is
not preserved — `film_directors` has no order column, matching every other
junction table); `writers` is also present but unused for now.

Populates `film_directors(film_id, person_id)`, joined on `tconst` =
`films.imdb_id`. Directors who were never personally nominated don't exist
in `people` yet at this point in the sync — they're INSERTed (`kind =
'person'`), with name/birth_year/death_year sourced from the same
name.basics snapshot used for Source 3. 1,508 such directors were added
2026-07-09.

Sync semantics (`src/enrich_imdb.py`, `sync_film_directors`, run after
`sync_people` since it depends on the person imdb_id linkage that step
builds): keyed on imdb_id throughout; re-runnable (`INSERT OR IGNORE` on
the junction).

Coverage: of 5,264 films with an imdb_id, 4 weren't in the title.crew
snapshot at all — confirmed via `zgrep`, not just an unfilled field — and a
further 74 are matched but list no directors. Spot-checking a range of the
74 on imdb.com directly confirmed IMDb itself doesn't know (mostly obscure
shorts/newsreels/documentaries, 1930-1989); for the 4 fully-missing titles,
3 were hand-verified online and fixed directly (San Francisco → W.S. Van
Dyke, Mrs. Miniver → William Wyler, 7 Faces of Dr. Lao → George Pal, all
already `people` rows from their own nominations — see CLAUDE.md "Resolved
data quirks"); Wings (tt0018578) remains unresolved. 5,189 films end up
with >=1 director linked, 6,400 links across 3,213 distinct directors.

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
- Directors are not a column on films: co-directors exist, so `film_directors`
  is a junction table (Source 4), not derived by query — it also covers
  directors who were never personally nominated.

## Scale (actual)

ceremonies 98 · categories 66 (seeded) · nominations 12,137 · films 5,265 ·
people 11,145 (10,839 persons + 306 companies) · nomination_films 10,879 ·
nomination_people 18,823 · film_directors 6,400.
Films enrichment: imdb_id 5,264 · release_year 5,265 · original_title
5,264 · runtime_minutes 5,252. People enrichment: imdb_id 10,108 persons
(+71 company `co` IDs) · birth_year 6,785 · death_year 4,087 — persons
include 1,508 directors never individually nominated, added by the
film_directors sync 2026-07-09.
Total ~65k rows, a few MB — trivial for SQLite.
