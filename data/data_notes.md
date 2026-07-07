# Data Notes (Data Dictionary)

Source: `DLu/oscar_data` on GitHub (BSD 2-Clause). Community dataset parsed from
the official Academy site (awardsdatabase.oscars.org) with IMDb IDs merged in.
Not official; spot-check against the official site when in doubt.

## Source file quirks (`data/oscars.tsv`)

- **Tab-separated** despite the original `.csv` name.
- 12,138 lines = 1 header + 12,137 nominations. One row = one nomination.
- Multi-valued cells are **pipe-separated** (`|`). `Film`/`FilmId` and
  `Nominees`/`NomineeIds` are exploded via junction tables (`nomination_films`,
  `nomination_people`). `Detail`/`Note`/`Citation` are NOT exploded — they stay
  as single verbatim TEXT columns on `nominations`, pipes and all, since
  schema.sql has no per-film/per-person junction for them.
- Unknown IMDb IDs appear as `?` → convert to NULL on ingestion.
- `Winner` is `True` or empty → store as INTEGER 0/1 (SQLite has no BOOLEAN).

## Column semantics

- **Ceremony**: ordinal integer (1–98). 1st ceremony (held 1929) honored films
  of 1927/28.
- **Year**: ceremony's honored-year label (e.g. "1927/28"). NOT necessarily a
  film's release year; release year must come from IMDb enrichment later.
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

## Design decisions

- **Fact vs dimension data.** Facts (nominations, films, people: thousands of
  rows) are parsed from the dataset — it is the authority. Dimensions
  (categories: 66 rows we make editorial decisions about) are curated seed
  data in `data/categories_seed.tsv` — we are the authority. Ingestion
  therefore VALIDATES categories rather than creating them: an unknown
  CanonicalCategory crashes the run (KeyError) so a human classifies it.
  Trade-off accepted: the seed is coupled to DLu's exact spellings, and an
  upstream rename breaks ingestion loudly — which beats silent misclassification.
- **Category hierarchy**: raw_category → source_name (66) → award_group
  (37, official-site facets) → class (8). Judgment calls in the mapping are
  documented in schema.md.
- **Surrogate integer primary keys** everywhere; `imdb_id` is nullable-but-unique
  (can be unknown, so it can't be the PK).
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

## Scale (actual, post-ingestion)

ceremonies 98 · categories 66 (seeded) · nominations 12,137 · films 5,265 ·
people 9,663 · nomination_films 10,879 · nomination_people 18,823.
Total ~57k rows, a few MB — trivial for SQLite.
