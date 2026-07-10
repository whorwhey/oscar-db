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
- IMDb non-commercial datasets (title.basics.tsv.gz, name.basics.tsv.gz,
  title.crew.tsv.gz; gitignored, re-downloadable from
  datasets.imdbws.com): authority for film titles (primaryTitle),
  original_title, release_year, runtime_minutes; people names
  (primaryName), birth_year, death_year; film_directors links.
  Joined on imdb_id.
- Us: categories seed (66 rows, data/categories_seed.tsv), hand fixes
  for cases neither source gets right (see "Resolved data quirks").
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
- src/people_id_review.py: regenerates data/people_no_imdb_id.txt, the
  ranked review list of persons without an imdb_id (749; candidates by
  exact-name match against name.basics, verified via knownForTitles).

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
- person 5614 Roderick Jaynes (the Coens' editing pseudonym): DLu packed
  both brothers' ids ("nm0001053,nm0001054"); fixed to the pseudonym's
  own record nm4093272.
- 10 stale person imdb_ids (IMDb retired/merged records, Summer-of-Soul
  style) hand-corrected 2026-07-09; Jeong Hoon Seo → nm8339190,
  user-picked among 4 IMDb namesakes.
- people 6162/6163: DLu had Al Mayer Jr.'s id on Sr.'s row; IMDb has
  both — Sr. nm4869190 (1936–2018), Jr. nm2353419 (b. 1966).
- 25 duplicate person rows merged 2026-07-09 (people 9,663 → 9,638): DLu
  lacks ids for recent SciTech honorees, so the same engineer entered
  once with and once without an id; ingest's name-dedupe is
  case-sensitive and spans only id-less rows (see data_notes.md).
- 230 id-less organizations reclassified kind='company' 2026-07-09 by
  award-context review (id-less rows defaulted to 'person'); kind is no
  longer purely id-prefix-derived. companies 71 → 301.
- people.name follows IMDb primaryName since 2026-07-09 (same decision
  as titles, 1,101 rows synced); Academy display text preserved on
  nominations.official_name. ~180 missing ids recovered by exact-name
  matching verified via knownForTitles overlap.
- 4 films (imdb_id confirmed present in title.basics) are entirely absent
  from the title.crew.tsv.gz snapshot (verified via zgrep, not just an
  unfilled field) — an IMDb export gap. 3 hand-fixed 2026-07-09 after
  online verification: San Francisco (tt0028216) → W.S. Van Dyke
  nm0886754, Mrs. Miniver (tt0035093) → William Wyler nm0943758, 7 Faces
  of Dr. Lao (tt0057812) → George Pal nm0657162 (all pre-existing people
  rows, nominated in their own right). Wings (tt0018578) unresolved.
  Separately, 74 more films are matched in title.crew but list no
  directors (`\N`); spot-checking a spread of these on imdb.com directly
  confirmed IMDb itself doesn't have the data (mostly obscure
  shorts/newsreels/documentaries) — not pursuing title.principals.tsv.gz
  for these, low yield for the size/effort.
- 4 more id-less "person" rows reclassified kind='company' 2026-07-10,
  found while triaging data/people_no_imdb_id.txt's no-match group: Rko
  Radio Pictures, Rko Radio, PARAMOUNT PICTURES, Paramount Pictures —
  studio names missed by the reclassification regex (no "pictures" or
  "radio" keyword). companies 301 → 305, persons 10845 → 10841.
  title.principals.tsv.gz's category field checked empirically (live
  ~640K-row sample) and confirmed closed to
  actor/actress/writer/director/cinematographer/producer/editor/composer/
  production_designer/self/archive_footage/casting_director/
  archive_sound — no technical-crew category exists, so it can't help
  disambiguate the Sci-Tech engineers filling data/people_no_imdb_id.txt;
  ruled out rather than downloading the 773MB file.
- First batch of the "ambiguous name matches" group resolved 2026-07-10
  (name.basics exact-name match found 2+ candidates): 13 imdb_ids
  hand-fixed after narrowing candidates by profession + birth/death
  plausibility (all rows are filmless Sci-Tech citations, so knownForTitles
  overlap can't disambiguate) and, for 3, positive external confirmation
  (John Neary's Wikipedia bio matches his Dolby CP500 citation exactly;
  Carl Ludwig traced via his own career bio from Celco digital film
  recorders to Blue Sky Studios co-founder; Wally Mills matched to the
  real Cinemills lighting company, distinct from an unrelated "Wally
  Mills, Actor" IMDb profile). The Carl Ludwig lookup collided with an
  imdb_id already on person 8283 "Carl Ludwig" (2016 CGI Studio renderer
  nomination) — his 2001 CELCO award turned out to be the same person,
  DLu-duplicated across two nominations like the 25 rows merged
  2026-07-09; person 6322 merged into 8283 rather than assigned a
  (colliding) id of its own. Person 814 "Paramount" turned out to be
  the studio again (citation names "PARAMOUNT STUDIO LABORATORY" across
  4 different nominations) — reclassified kind='company', same as the
  4 fixed above. Person 5926 "Ronan Carroll" left unresolved: the sole
  narrowed candidate is a confirmed film composer, not the Milo
  Motion-Control Crane engineer the citation describes — conflicting
  evidence, not written. persons 10841 → 10839, companies 305 → 306,
  people total 11146 → 11145 (net -1 from the merge).

## Roadmap

1. Finalize data/people_no_imdb_id.txt (next chat): 132 ambiguous name
   matches + 617 no-match (610 + 7 company-looking) still open.
2. Interface demos (chat after that): canned queries, small CLI,
   text-to-SQL LLM demo. GUI = VS Code SQLite Viewer extension. Respect
   the Titanic disambiguation rule above. User wants this framed as a
   lecture + demo, not just a code drop.
3. Remaining enrichment: title_zh/name_zh, douban_id, countries. For
   countries specifically, agreed approach (2026-07-09): use
   title.akas.tsv.gz, the row per title with isOriginalTitle=1, to get
   both region and language in one shot — but check empirically first
   whether that row actually carries non-null region/language (may
   instead be null there, with real values only on the *localized*
   akas rows). Validate against the small ground-truth set we already
   have for free: International Feature Film nominees, where the
   official "nominee" is the country itself (data_notes.md).

Rebuild/merge tooling (previously a possible future item): dropped by
agreement 2026-07-09 — the db itself is the durable artifact going
forward, not the ingest pipeline; next new data (e.g. a future
ceremony) will be added directly against the live db, not via a fresh
TSV rebuild.

Done 2026-07-08: original_title + runtime_minutes columns, enriched
from IMDb (enrich_release_year.py generalized into enrich_imdb.py);
data_notes.md rewritten around the sources; README db-structure
subsection.

Done 2026-07-09: people enrichment (was roadmap item 1) — birth_year/
death_year columns synced from name.basics; enrich_imdb.py split into
sync_films/sync_people; name follows primaryName; ~180 ids recovered,
25 duplicate rows merged, 230 orgs reclassified as companies, 13 wrong
ids hand-fixed; src/people_id_review.py added.

Done 2026-07-09: film_directors junction (film_id, person_id), from
title.crew.tsv.gz via enrich_imdb.py's new sync_film_directors — 6,400
links, 5,189 films, 3,213 directors; 1,508 directors never personally
nominated INSERTed into people (kind='person', named/dated from
name.basics); pinned counts in verify.py/data_notes/README updated. 3
of 4 IMDb crew-file gaps hand-fixed (see "Resolved data quirks"); 74
films with a genuinely-unknown-to-IMDb director confirmed by spot-check,
left as-is.
