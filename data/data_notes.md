# Data Notes (Sources & Data Dictionary)

The database draws on **two authorities, across five files**:

1. **DLu's TSV** (`data/oscars.tsv`) — the authority for which
   ceremonies/nominations/films/people exist and how they connect.
   Bootstrap-only (ingested once, never routinely reloaded).
2. **IMDb non-commercial datasets** — the authority for enrichment,
   re-runnable via `src/enrich_imdb.py`. Four gitignored, re-downloadable
   files:
   - `title.basics.tsv.gz` — film titles, original titles, release years, runtimes
   - `name.basics.tsv.gz` — people names, birth/death years
   - `title.crew.tsv.gz` — film-director links
   - `title.akas.tsv.gz` — Chinese titles (rows where `region='CN'`)

Categories are not sourced at all — we author them (see "Categories:
curated by us" below).

Working rules and the authority summary live in CLAUDE.md; schema rationale
in schema.md. This file is the deeper reference — each source file gets its
own section below.

## Source 1: DLu's TSV (bootstrap)

`DLu/oscar_data` on GitHub (BSD 2-Clause). Community dataset parsed from the
official Academy site (awardsdatabase.oscars.org) with IMDb IDs merged in.
Not official; spot-check against the official site when in doubt.

Bootstrap-only: ingested once by `src/ingest.py`, never routinely reloaded —
`oscars.db` is the maintained artifact, and reloading would destroy
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

### Known gap: `kind` classification is still incomplete

Found 2026-08-05, incidentally, during text-to-SQL eval work (not
a systematic audit) — see `docs/text_to_sql_prompt_log.md`, eval case 6: person_id
1925, `ROY C. STEWART AND SONS`, is stored with `kind = 'person'` despite
being obviously a business name ("AND SONS"). This is the same class of
defect as the 230 id-less organizations reclassified to `kind = 'company'`
2026-07-09 and the 4 more caught 2026-07-10 (see docs/project_history.md
"Resolved data quirks") — this one just wasn't caught by either pass. Since both of those
passes were manual/regex-assisted review rather than exhaustive
verification, at least one more row slipping through means the
`kind = 'person'` set has not been fully audited and likely still contains
other undetected company rows. Not fixed here — flagging for a future
`kind`-audit pass, scoped like the earlier ones (review id-less
`kind = 'person'` rows for company-like naming patterns: "AND SONS",
"INC", "CORP", "STUDIOS", "PICTURES", etc., beyond the keywords the
2026-07-09/07-10 regex already covered).

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
quirks" in docs/project_history.md.

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

Coverage: 10,100 of 10,836 persons have an imdb_id, every one matching a
name.basics row; 6,785 have birth_year, 4,087 death_year. The 736 ID-less
persons — mostly pre-1960s SciTech honorees with no IMDb record — were
a bulk review effort (roadmap item 1, closed 2026-07-14, not resumed as
a bulk technique; its worklist and generator script were removed
2026-07-17). ~180 IDs were recovered 2026-07-09 by exact-name matching
verified against knownForTitles, and 5 more 2026-07-11 by individual
research, see docs/project_history.md "Resolved data quirks"; a
further ~26 recovered the same way were reverted after review —
elimination-only matching without independent confirmation isn't
trusted here).

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
already `people` rows from their own nominations — see
docs/project_history.md "Resolved data quirks"); Wings (tt0018578)
remains unresolved. 5,189 films end up with >=1 director linked, 6,400
links across 3,213 distinct directors.

## Source 5: IMDb title.akas (enrichment)

`title.akas.tsv.gz` from datasets.imdbws.com, ~480MB, gitignored,
re-downloadable; current snapshot 2026-07. One row per (title, region,
language, ...) alternate-title combination; `titleId` = `films.imdb_id`.
Rows filtered to `region = 'CN'` — the source for `films.title_zh` (a
different angle on this same file, matching original-title text across
all regions to infer country/language, was tried and dropped 2026-07-14,
see docs/project_history.md; that finding doesn't apply here since
this is a direct region filter, not text matching).

Not every film has a CN row, and CN rows aren't reliably real Chinese
text — IMDb tags some pinyin/English rows `region=CN` too (e.g. Solo:
A Star Wars Story's CN row is "Ranger Solo", not Chinese at all).
Written to `films.title_zh` (`src/enrich_imdb.py`, `sync_title_zh`) when:
1. exactly one CN row exists and it contains CJK text, or
2. 2+ CN rows exist but exactly one is `types='imdbDisplay'` (IMDb's own
   designated display title for the region) *and* that row contains CJK
   text — the CJK check applies here too, since a lone imdbDisplay row
   can itself be pinyin (Crouching Tiger, Hidden Dragon's only imdbDisplay
   row is "Wo hu cang long"; the real title, 卧虎藏龙, is typed
   `alternative` and had to be hand-picked — see
   docs/project_history.md).

Anything left ambiguous by those two rules (no CN row, a lone non-CJK
row, or 0/2+ qualifying imdbDisplay rows) is left NULL. 1,311 films were
written algorithmically 2026-07-17 (1,017 + 294); 13 more were reviewed
and hand-picked from their candidate rows (data/title_zh_review.md,
docs/project_history.md "Resolved data quirks"), one of them
(Maleficent: Mistress of Evil) with a value that isn't in title.akas at
all — a genuine hand entry, not IMDb-sourced. films.title_zh filled:
1,324 of 5,264 films with an imdb_id; the remaining 3,940 are a
permanent, expected gap, not being pursued further as a bulk technique
(same posture as the person/company imdb_id gaps closed 2026-07-14).

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
- `title_zh` / `name_zh` hold Simplified Chinese (zh-Hans). `title_zh`
  filled 2026-07-17 from IMDb title.akas where unambiguous, see Source 5;
  `name_zh` still NULL, planned from Douban.
- `douban_id` NULL for now; Douban has no official API — future scraping lesson.
  Some films will never have one (too obscure, or censored).
- Directors are not a column on films: co-directors exist, so `film_directors`
  is a junction table (Source 4), not derived by query — it also covers
  directors who were never personally nominated.

## Scale (actual)

ceremonies 98 · categories 66 (seeded) · nominations 12,137 · films 5,265 ·
people 11,144 (10,836 persons + 308 companies) · nomination_films 10,879 ·
nomination_people 18,823 · film_directors 6,400.
Films enrichment: imdb_id 5,264 · release_year 5,265 · original_title
5,264 · runtime_minutes 5,252. People enrichment: imdb_id 10,100 persons
(+71 company `co` IDs) · birth_year 6,785 · death_year 4,087 — persons
include 1,508 directors never individually nominated, added by the
film_directors sync 2026-07-09.
Total ~65k rows, a few MB — trivial for SQLite.
