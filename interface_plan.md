# Interface & Demo Plan

Decided 2026-07-20. Context: planning session for what to build on top
of `oscars.db` now that the schema, ingestion, and enrichment are done.

## Goals

Learning project. The database is the product; interfaces are small
demos for learning SQL, prompt engineering, and tool usage. Not shipping
anything.

## Decided build order

### Phase 5a — Query collection (Chat + Jupyter)

Write 8–12 SQL queries covering core question shapes. Work in Jupyter
for immediate feedback. Document each query with explanations of the SQL
concepts it introduces. Save finished queries as `.sql` files in
`queries/`.

Target queries (roughly ordered by SQL complexity):
1.  List all ceremonies (basic SELECT + ORDER BY)
2.  Winners for a given category + year (WHERE + JOIN)
3.  All nominations for a person (multi-table JOIN)
4.  Most-awarded films (GROUP BY + COUNT)
5.  Most-nominated people who never won (subquery or LEFT JOIN)
6.  Person name search with disambiguation (LIKE + duplicates)
7.  Film title search with disambiguation (same pattern)
8.  Most wins across categories (aggregate + JOIN)
9.  Directors with most winning films, never nominated for Directing
    (multi-join: film_directors + nominations)
10. Category history — how names changed over years (raw_category)
11. Youngest/oldest winner (birth_year arithmetic)
12. Chinese title display with fallback (COALESCE)

Tool: Claude Chat (Sonnet). Upload `schema.sql` from repo.

### Phase 5b — CLI wrapper (Jupyter → Claude Code)

Python script that loads `.sql` files by name and runs them against
`oscars.db` with formatted output. The queries are already written and
tested from 5a.

Architecture: queries live in `.sql` files, CLI is a thin runner. The
CLI does not contain SQL — it loads it from disk.

Tool: Claude Code (Sonnet).

### Phase 5c — Datasette

`pip install datasette`, write `metadata.yaml` with canned queries
(referencing the `.sql` files from 5a), run `datasette oscars.db`.
Mostly configuration, little code.

Why Datasette over Flask/sql.js: zero code, native canned-query support,
Python-native, teaches the "introspect schema → auto-generate UI"
pattern. Free, local, no hosting needed.

Tool: Claude Code or solo.

### Phase 6 — Text-to-SQL LLM demo (Chat → Claude Code)

Design the prompt in Chat (Opus): what schema context to send the LLM,
how to handle ambiguity (duplicate titles, fuzzy names), safety checks.
Test by hand against known-good queries from 5a. Then build wiring in
Claude Code (Sonnet).

Tool: Claude Chat (Opus) for prompt design, Claude Code (Sonnet) for
implementation.

## Key decisions

- **Jupyter is the development scratchpad**, not a separate deliverable.
  Write and test SQL there; save proven queries as `.sql` files; CLI
  loads those files.
- **Datasette** chosen over Flask/FastAPI (too much web plumbing for the
  goal) and sql.js (requires JavaScript, different ecosystem).
- **Sonnet for routine work** (SQL teaching, CLI building). **Opus for
  judgment-heavy work** (text-to-SQL prompt engineering, complex design).
- **Start each Chat session** by uploading `schema.sql` from the repo
  (ground truth). The project-attached `schema.md` and `data_notes.md`
  are from the design phase and are stale on column details.

## Schema reminder (current state, per repo)

8 tables. 5 entity + 3 junction.

- `ceremonies` (98 rows)
- `categories` (66 rows, hierarchy: source_name → award_group → class)
- `films` (5,265 rows; title, original_title, title_zh, release_year,
  runtime_minutes, imdb_id, douban_id)
- `people` (11,144 rows; name, name_zh, kind, birth_year, death_year,
  imdb_id, douban_id)
- `nominations` (12,137 rows; is_winner, raw_category, detail, note,
  citation)
- `nomination_films`, `nomination_people`, `film_directors` (junctions)

Film titles are NOT unique. Always join/group by film_id.
