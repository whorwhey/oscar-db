# Schema

The design is settled: `schema.sql` is the authority, and this file explains
the *why*. Don't change the schema without discussing first (see CLAUDE.md).
For the tables and how they connect at a glance, see the diagram in the
README; this file goes column-by-column.

**Changelog**

- 2026-07-06 — Design finalized. Categories redesigned as curated seed data,
  no longer discovered from the source file (see "Category hierarchy" below).
- 2026-07-08 — `films` gained `original_title` + `runtime_minutes` (IMDb).
- 2026-07-09 — `film_directors` junction added (IMDb crew data).
- 2026-07-14 — `film_countries`/`person_countries` junctions removed
  (country/language enrichment dropped; see docs/project_history.md).

## Tables

films
  film_id        PK (integer, surrogate)
  imdb_id        nullable, unique        -- 'tt...'; '?' in source → NULL
  title          text, required          -- follows IMDb primaryTitle
  title_zh       nullable                -- Simplified Chinese (zh-Hans)
  douban_id      nullable
  release_year   nullable integer        -- IMDb startYear
  original_title nullable                -- IMDb originalTitle, verbatim; see
                                         -- data_notes.md
  runtime_minutes nullable integer       -- IMDb runtimeMinutes

people                                    -- includes companies (see kind)
  person_id      PK
  imdb_id        nullable, unique        -- 'nm...' person / 'co...' company
  name           text, required          -- follows IMDb primaryName; see
                                         -- data_notes.md
  name_zh        nullable                -- zh-Hans
  douban_id      nullable
  kind           'person' | 'company'    -- ID prefix at ingestion + hand
                                         -- review of ID-less rows
  birth_year     nullable integer        -- IMDb birthYear
  death_year     nullable integer        -- IMDb deathYear; NULL = unknown
                                         -- or alive

categories                                -- CURATED seed data, not parsed
  category_id    PK
  source_name    text, unique, required  -- exact CanonicalCategory string in
                                         -- the DLu dataset; join key for
                                         -- ingestion. Merged across years but
                                         -- still historical (e.g. SOUND
                                         -- RECORDING), not modern.
  award_group    text, required          -- official-site facet, curated by us
  class          text, required          -- coarse group, curated by us

ceremonies
  ceremony       PK (integer ordinal, 1–98)
  year_label     text                    -- e.g. '1927/28'

nominations                               -- main table; one row per source row
  nomination_id  PK
  ceremony       FK → ceremonies
  category_id    FK → categories
  raw_category   text                    -- name as written that year
  official_name  text                    -- source 'Name' display string
  is_winner      integer 0/1
  detail         nullable
  note           nullable
  citation       nullable

## Junctions (many-to-many)

nomination_films   (nomination_id FK, film_id FK)
nomination_people  (nomination_id FK, person_id FK)
film_directors     (film_id FK, person_id FK)   -- from IMDb crew data,
                                                 -- independent of nomination
                                                 -- history; see data_notes.md
                                                 -- Source 4

## Category hierarchy

Four levels of granularity, finest to coarsest:

  raw_category (per-year text, on nominations)
    → source_name (66, DLu's CanonicalCategory; fidelity to source)
      → award_group (37, official awardsdatabase.oscars.org facets; the
        usual query level, e.g. all Cinematography with B&W/Color merged)
        → class (8: Acting, Directing, Music, Production, Writing, Film,
          SciTech, Special)

categories is dimension data: 66 stable rows we make editorial decisions
about, so it is seeded from `data/categories_seed.tsv` (source of truth
for the mapping), not discovered during parsing. The dataset's own Class
column is ignored — award_group and class are ours. Ingestion validates
instead of creating: a CanonicalCategory absent from the seed crashes the
run (KeyError), forcing a human to classify it. This couples the seed to
DLu's exact spellings; breaking loudly on upstream renames is intended.

Curation judgment calls (verify against the official site if in doubt):
- SOUND RECORDING → Sound Mixing (lineage of the same award)
- Class I/II/III → the three modern SciTech tiers (old names, same tiers)
- MEDAL/AWARD OF COMMENDATION → Bonner Medal group
- SPECIAL FOREIGN LANGUAGE FILM AWARD → Honorary Award group (keeps every
  group inside one class; mapping it to International Feature would not)
- class "Film" = awards honoring the film itself (dataset called it Title)

## Display rule

Chinese-with-English-fallback is computed, never stored:
  SELECT COALESCE(title_zh, title) AS display_title FROM films;
