# Project history

Chronological log of completed/dropped roadmap work and the detailed
record of hand-resolved data quirks for oscar-db. Split out of
CLAUDE.md 2026-08-09 to keep the root file focused on active working
instructions; see CLAUDE.md for current scope, data authority, and
schema rules.

## History (one line each; "Resolved data quirks" below has full detail)

- 2026-07-08 — Done: original_title + runtime_minutes columns from IMDb;
  enrich_release_year.py generalized into enrich_imdb.py; data_notes.md
  rewritten around the sources.
- 2026-07-09 — Done: people enrichment — birth_year/death_year from
  name.basics; name follows primaryName; ~180 ids recovered, 25 duplicate
  rows merged, 230 orgs reclassified company, 13 wrong ids hand-fixed.
- 2026-07-09 — Done: film_directors junction from title.crew.tsv.gz —
  6,400 links / 5,189 films / 3,213 directors; 1,508 never-nominated
  directors added to people (3 of 4 crew-file gaps hand-fixed, 74
  genuinely-unknown directors left as-is).
- 2026-07-09 — Dropped: rebuild/merge tooling — the live db is the
  durable artifact; new data (e.g. a future ceremony) is added against it,
  not via a fresh TSV rebuild.
- 2026-07-11 Paused → 2026-07-14 Closed: roadmap item 1 (people/company
  imdb_id enrichment) retired as a bulk effort. 5 ids resolved with
  independent confirmation, 10 studio rows reclassified company; ~26
  elimination-only matches reverted. Lesson: profession/era elimination
  without independent confirmation isn't trusted here. Remaining gaps
  (736 persons, 237 companies) left NULL, accepted as permanent.
- 2026-07-14 — Dropped: country/language enrichment via title.akas — no
  independently-verifiable region/language signal survives in this
  catalog (checked empirically; the film_countries/person_countries
  junctions were dropped from schema.sql and oscars.db).
- 2026-07-17 — Done: title_zh from title.akas region='CN' — 1,324 of
  5,264 films filled (1,017 single-row + 294 imdbDisplay tie-break + 13
  hand-picked); the remaining 3,940 a permanent, expected gap.
- 2026-07-17 — Cleanup: removed the retired people_id_review worklist +
  its generator script; moved oscars.db from data/ to the repo root (it's
  the product, not a data input).
- 2026-07-22 — Done: Phase 5a query collection — notebooks/oscar_sql_
  tutorial.ipynb, 19 tested queries in Parts 0–8 (SELECT/ORDER BY/WHERE/
  LIKE/params/JOIN/LEFT JOIN/GROUP BY/aggregates/HAVING/subqueries/CTEs/
  COALESCE/CASE); pandas (runtime) + ipykernel (dev) deps added;
  interface_plan.md added.
- 2026-07-23 — Done: Phase 5b CLI — src/query.py, a thin runner loading
  queries/*.sql and running them vs oscars.db (pandas output, manual
  sys.argv, no argparse). Two parameterized lookups extracted from the
  tutorial: queries/person_history.sql, queries/title_search.sql. Scoped
  to parameterized lookups only (canned reports deferred to Datasette).
  Match-quality feedback: separator-loosening LIKE pattern (build_pattern),
  a "loose match" note when the term isn't a literal substring of any hit,
  and difflib did-you-mean (n=2) on empty results. interface_plan.md
  Phase-5a rewritten target-list→as-built, Phase-5b marked done. queries/
  now holds 2 files; the tutorial's other queries not bulk-extracted
  (CLI scope is deliberately narrow).
- 2026-07-27 — Done: Phase 5c Datasette — metadata.yaml (repo root) +
  `datasette` added to `[dependency-groups] dev`; run via `uv run
  datasette oscars.db -m metadata.yaml`. 7 canned queries adapted from
  the notebook's report-style cells (most_awarded_films,
  most_nominations_no_win, most_categories_won, category_history
  parameterized, youngest/oldest_acting_winners split in two,
  acting_wins_by_age_bracket); SQL inlined directly in metadata.yaml
  since canned queries can't reference a `queries/*.sql` file path — not
  re-extracted from the CLI's 2 lookup files either, to avoid a second
  driftable copy of the same SQL.
- 2026-08-06 — Done: Phase 6 text-to-SQL — closes the full
  interface_plan.md build order (5a query collection → 5b CLI → 5c
  Datasette → 6 text-to-SQL), all done; interface demos retired as a
  roadmap item. `prompts/system_prompt.txt` (v0.8) iterated in Chat
  (Opus) over 11 test cases + 4 stretch cases, 7 fix rounds, full
  changelog and per-case SQL/result/verdict in `phase6_prompt_log.md`.
  `src/text_to_sql.py` built against CBORG (LBNL's LiteLLM gateway,
  `CBORG_API_KEY`, `https://api.cborg.lbl.gov`) rather than direct
  Anthropic — the `anthropic` SDK works unmodified, only `base_url`/
  `api_key` differ. CBORG's $50/month budget meters commercial Claude
  calls (~85% spent when this was wired in), so a `--model NAME` flag
  lets eval runs target CBORG's free `lbl/*`-prefixed on-prem models
  instead of the default `claude-sonnet-5`; full config recorded in
  `phase6_notes.md`'s "CBORG configuration" section after being
  re-derived from scratch twice across session restarts — check there
  first before rediscovering it a third time. Also dropped: extracting
  the notebook's remaining ~10 queries to `queries/*.sql` as a
  standalone collection (Phase 5a leftover) — every consumer that would
  read from it already got what it needed a different way (5b's 2
  files, 5c's 7 inlined into metadata.yaml), so it would only be a
  second, driftable copy of code already tested in the notebook.
- 2026-08-08 — Done: repo restructure for external readability now that
  the interface-demo build order is closed. `interface_plan.md` deleted
  (a superseded planning journal — its decisions are already condensed
  into this History section). `phase6_notes.md` → `docs/text_to_sql.md`
  and `phase6_prompt_log.md` → `docs/text_to_sql_prompt_log.md`,
  renamed off the phase-numbered names and moved out of the root;
  `docs/text_to_sql.md` additionally pruned of its now-stale "Build
  sequence" and "Files the Code agent needs" sections (build-time
  instructions to a coding agent, not reference material). The CBORG
  configuration section referenced above is now at
  `docs/text_to_sql.md`, not `phase6_notes.md`.
- 2026-08-09 — Cleanup: this file split out of CLAUDE.md — the History
  and Resolved data quirks sections moved here verbatim, CLAUDE.md
  trimmed to active scope/data-authority/schema/roadmap content only.
  Motivation: a stranger browsing the repo root was hitting a 22KB
  AI-agent work log before any human-facing doc; splitting keeps
  CLAUDE.md's root-level auto-load (Claude Code loads CLAUDE.md from
  the project root every session) while moving the bulk of stale detail
  to a reference doc alongside schema.md and data/data_notes.md.

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
- Second batch of the same narrowed-to-1 tier, same day: Isaac Reuben
  (nm2210750) confirmed via a direct, non-coincidental link — Shotgun
  Software (his 2019 Sci-Tech award) was founded specifically to build
  a pipeline tool for Disney's The Wild, which is this candidate's only
  IMDb credit. Anthony Seaman, Peter Janssens and Peter Litwinowicz
  written on clean-elimination confidence (real person independently
  confirmed to exist — LinkedIn engineering practice, Barco-adjacent
  Flemish short film, RE:Vision Effects co-founder bio, respectively —
  but the exact nconst-to-bio link isn't independently provable beyond
  the namesake elimination). Daniel Wilk and Dave Sherwin left
  unresolved despite the real honorees being well-documented (Adobe
  Principal Scientist; Panavision Power Pod co-inventor) — their sole
  surviving name.basics candidates carry credits (German TV camera
  crew; a 1997 documentary's sound department) that don't fit those
  careers, so the coincidental-namesake risk outweighs the elimination
  logic. Person 6430 "GLENN SANDERS" (2002 Zaxcom award) merged into
  8291 "Glenn Sanders" (2016 Zaxcom award, same co-honoree Howard
  Stark both times) — another DLu per-nomination duplicate; nm7383728
  assigned to the surviving row. persons 10839 → 10838, imdb_id 10108 →
  10113, people total 11145 → 11144 (net -1 from the merge).
- First strong+medium batch of the "narrowed to 2-3" tier, same day (14
  imdb_ids): several with direct confirmation — Thomas Knoll (Photoshop)
  is literally interviewed in "From Darkroom to Daylight," his
  candidate's only IMDb credit; Jonathan Moulin's candidate has explicit
  ILM lighting/lookdev credits on Solo and Avatar: The Way of Water,
  matching his ILM citation exactly. Others (John Jurgens/Steadicam,
  Martin Werner/Maya Fluid Effects, Steve Linn/Rhythm & Hues, John
  Ellwood, Greg Smokler) matched on profession + era fit strong enough
  to treat as confirmed. Medium-confidence set (Ralph Chapman, Gary
  Stadler, Glenn Kennel, Paul Tate, Brent Bell, Chris Huntley, Dominique
  Boisvert) written on thematic/contextual fit without a fully
  independent identity check. Low-medium tier (Kenneth Richter, Roland
  Miller, Jack C. Smith, Lindsay Arnold, Mark Kirk) deliberately held
  back for review alongside 5926 Ronan Carroll, not written this round.
  Two more studio/company nominees found and reclassified: person 5166
  "Arnold Richter" (citation reads "To ARNOLD & RICHTER..." — ARRI's
  founding company name, mis-entered as a person) and person 8268
  "Sony" (literally the corporation). Person 4272 "Ruben Avila" merged
  into 4270 "RUBEN AVILA" (two related 1984 Film Processing Corp
  citations, same DLu per-nomination duplicate pattern) but left
  without an imdb_id — neither IMDb candidate fit either row (both were
  40-year-era mismatches), a duplicate merge doesn't require a resolved
  id. TECH_PROFESSIONS in people_id_review.py was missing
  "production_department" and "location_management" — caught mid-batch
  when Paul Tate's actual best candidate (right birth year, real 1990s
  film credits) turned out to be excluded from the narrowed list purely
  by that gap; fixed, which regenerates a few new narrowed-to-1 rows not
  yet reviewed. persons 10835/imdb_id 10127, companies 308, people total
  11143 (net -1 from the merge, -2 from the company reclassifications).
- User review 2026-07-11 rejected most of the two batches above as
  unreliable: elimination-only matching (no independent evidence beyond
  "sole plausible candidate after excluding actors/wrong-era namesakes")
  isn't trustworthy enough to write, full stop — same lesson already
  learned from Ronan Carroll/Daniel Wilk/Dave Sherwin, generalized.
  Reverted to NULL: all 26 "elimination-only" imdb_ids from the second
  batch (Wally Mills, John Jurgens, Martin Werner, Steve Linn, John
  Ellwood, Greg Smokler, Floyd Campbell, Colin Mossman, David Gilmartin,
  David W. Spencer, John Pond, Paul Kaufman, Kurt Singer, James
  Moultrie, Brian Dang, Jim Graves, Anthony Seaman, Peter Janssens,
  Peter Litwinowicz, Ralph Chapman, Gary Stadler, Glenn Kennel, Paul
  Tate, Brent Bell, Chris Huntley, Dominique Boisvert). Also reverted:
  the Glenn Sanders merge (6430/8291) — same-co-honoree-twice was judged
  not solid enough either; split back into two separate person rows,
  both NULL, 6430 re-inserted with its original person_id and its 2002
  nomination repointed back to it. Only the 5 rows with genuinely
  independent confirmation survive: John Neary (Wikipedia bio naming
  the exact award), Isaac Reuben (Shotgun/Disney's-The-Wild founding
  story), Thomas Knoll (subject of the documentary that's his
  candidate's only IMDb credit), Jonathan Moulin (candidate's own IMDb
  credits list ILM staff roles on the exact films cited), and the Carl
  Ludwig merge (his own career bio spans both awards). Working record
  of the reasoning kept in data/people_review_pending.md (untracked).
  persons 10836/imdb_id 10100, companies 308/71, people total 11144.
  Lesson: profession/era elimination alone, without a positive external
  or cross-citation confirmation, should not be written — flag as
  unresolved instead, even at the cost of leaving the row NULL.
- title_zh enrichment 2026-07-17 from title.akas.tsv.gz (region='CN'):
  written when a film has exactly one CN row containing CJK text, or 2+
  CN rows but exactly one is types='imdbDisplay' *and* contains CJK text
  (a lone imdbDisplay row can itself be pinyin/English, not just a lone
  plain row — see Crouching Tiger below). 1,311 films written this way
  (1,017 single-row + 294 imdbDisplay tie-break). 13 films stayed
  ambiguous after that rule and were hand-reviewed/hand-picked from
  their candidate CN rows (data/title_zh_review.md has the full
  candidate lists): Of Human Bondage 人生的枷锁, Ninotchka 妮诺契卡, The
  Young Philadelphians 文君怨, The V.I.P.s 大人物, Bonnie and Clyde
  雌雄大盗, North Country 决不让步, The Class 墙壁之间, Godzilla Minus
  One 哥斯拉-1.0, Shaun the Sheep Movie 小羊肖恩, Parasite 寄生虫, Better
  Days 少年的你. Crouching Tiger, Hidden Dragon (tt0190332) also hand-
  picked: its sole imdbDisplay row is pinyin ("Wo hu cang long"), so the
  algorithm skipped it even though a clean CJK alternative-typed row
  (卧虎藏龙) existed — this pattern (checked empirically, only this one
  case in the dataset) is why the CJK filter applies to the imdbDisplay
  pick too, not just lone rows. Maleficent: Mistress of Evil (tt4777008)
  is a genuine hand-entry exception: 沉睡魔咒2 is not present anywhere in
  its title.akas CN rows (which only have a pinyin and an English row) —
  entered from outside knowledge, not IMDb-sourced, unlike every other
  title_zh value. films.title_zh filled: 1,324 of 5,264 imdb_id'd films;
  3,940 remain NULL (no CN row at all, or a single/imdbDisplay CN row
  with no real CJK text) — same permanent-gap posture as the person/
  company imdb_id gaps closed 2026-07-14, not being pursued further as
  a bulk technique.
