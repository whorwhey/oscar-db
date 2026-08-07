# Interface & Demo Plan

Decided 2026-07-20. Context: planning session for what to build on top
of `oscars.db` now that the schema, ingestion, and enrichment are done.

## Goals

Learning project. The database is the product; interfaces are small
demos for learning SQL, prompt engineering, and tool usage. Not shipping
anything.

## Decided build order

### Phase 5a — Query collection (Chat + Jupyter) — content-complete

Built as `notebooks/oscar_sql_tutorial.ipynb`: 20 worked queries across
Parts 1–8 (Part 0 is connection setup), organized **by SQL syntax
family** rather than the original question-ordered list below — each
part introduces one new concept on top of the last, which reads better
as a tutorial than grouping by question type.

- **Part 1 — Reading from one table:** SELECT/ORDER BY/LIMIT (1.1);
  DISTINCT (1.2)
- **Part 2 — Filtering rows:** WHERE + LIKE, incl. the Titanic
  disambiguation case (2.1); `?` parameters (2.2); IS NULL (2.3)
- **Part 3 — Combining tables:** JOIN (3.1); chained JOIN + parameter,
  a person's full nomination history (3.2); LEFT JOIN for never-
  nominated directors (3.3)
- **Part 4 — Aggregating:** GROUP BY + COUNT, most-awarded films (4.1);
  SUM + HAVING, most nominations without a win (4.2); COUNT(DISTINCT) +
  GROUP_CONCAT, most categories won (4.3); MIN/MAX, category-name
  history (4.4)
- **Part 5 — Set membership:** IN with a dynamically built list, wins
  across two categories (5.1)
- **Part 6 — Subqueries:** NOT IN (6.1); scalar subquery (6.2); IN
  nested inside NOT IN (6.3); OR/AND across category-hierarchy levels
  (6.4) — all built around "Best Picture winners missing some other
  nomination," layering in complexity
- **Part 7 — Alternative patterns:** NOT EXISTS restating 6.1 (7.1); a
  named CTE (`WITH`) restating 6.4 (7.2)
- **Part 8 — Computed columns:** arithmetic, youngest/oldest winners
  (8.1); COALESCE, Chinese-title fallback (8.2); CASE WHEN, age
  brackets (8.3)

Differences from the original 12-query target list (kept below for
reference): reorganized by syntax instead of by question; person/film
disambiguation search (#6/#7) and category-history (#10) got folded
into 2.1 and 4.4 rather than staying standalone; Parts 5–7 (set
membership, subqueries, alternative patterns) weren't in the original
plan — added because the Best-Picture-winners question thread needed
them, and turned into a natural excuse to also teach subquery-vs-EXISTS
and CTEs. #9 (directors with most winning films, never nominated for
Directing themselves — a `film_directors` + `nominations` multi-join)
was dropped, not built or folded in anywhere; the closest thing that
exists is 3.3's simpler "never-nominated directors" via LEFT JOIN.

**Dropped 2026-08-06:** extracting the rest of the notebook's proven
queries to `queries/*.sql` as a standalone collection. Every consumer
that would have read from it already got what it needed a different
way — Phase 5b extracted the 2 parameterized lookups it uses
(`person_history.sql`, `title_search.sql`); Phase 5c needed 7 more but
`metadata.yaml` can't reference a file path, so those got inlined into
`metadata.yaml` directly instead. That leaves ~10 of the notebook's ~20
queries (the plain JOIN/subquery/CTE teaching examples) with no
consumer in the repo at all — extracting them now would just be a
second, driftable copy of code already tested and documented in the
notebook, for nothing to read it. Same "no second copy" reasoning
Phase 5c itself used to justify not re-extracting the CLI's 2 files.

Tool used: Claude Chat (Sonnet), schema.sql uploaded per session.

<details>
<summary>Original target list (superseded, kept for reference)</summary>

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

</details>

### Phase 5b — CLI wrapper (Jupyter → Claude Code) — done

Built as `src/query.py` (thin runner, no SQL in Python — loads and runs
`.sql` files from disk via `pandas.read_sql_query`) plus two query files
in `queries/`:

- `queries/person_history.sql` — a person's full nomination history,
  adapted from notebook 3.2. Uses `LIKE` (not 3.2's exact `=`) so the
  CLI works without knowing exact IMDb capitalization; adds
  `person_id`/`name` to the SELECT so same-name collisions are visible
  rather than silently merged (parallels the Titanic rule below).
- `queries/title_search.sql` — notebook 2.1 as-is, hardcoded
  `'%Titanic%'` replaced by a `?` placeholder.

Scoped deliberately narrow — **parameterized lookups only**, not canned
reports: a no-argument report browser would duplicate Phase 5c
(Datasette), which exists specifically for that job. Usage:
```
uv run src/query.py person-history "Daniel Day-Lewis"
uv run src/query.py title-search "Titanic"
```
No argparse (matches `src/ingest.py`/`src/verify.py`'s manual `sys.argv`
convention); no query name/missing arg prints usage and exits 1.

Match-quality feedback (a small `QUERIES` registry maps each query to its
searched table+column, which powers this):
- `build_pattern()` loosens separators — word-tokens rejoined with `%`,
  so `"Daniel Day Lewis"` finds `Daniel Day-Lewis`.
- When results are only a loose match (the raw term isn't a literal,
  case-insensitive substring of any hit), a one-line `note:` flags it —
  case-only differences like `titanic` vs `Titanic` don't trigger it.
- On zero results, `difflib.get_close_matches` (stdlib) against the
  searched column suggests near-misses: `no matches for 'Daniel
  Day-Lawis'. Did you mean: Daniel Day-Lewis?` — plain "no matches" when
  nothing is close.

Tool: Claude Code (Sonnet).

### Phase 5c — Datasette — done

Built as `metadata.yaml` (repo root, alongside `oscars.db`), plus
`datasette` added to `[dependency-groups] dev` in `pyproject.toml`
(`uv add --group dev datasette`). Run via `uv run datasette oscars.db
-m metadata.yaml`.

7 canned queries, adapted from the notebook's report-style questions
that Phase 5b deliberately left out of the CLI: `most_awarded_films`
(4.1), `most_nominations_no_win` (4.2), `most_categories_won` (4.3),
`category_history` (4.4, parameterized), `youngest_acting_winners` /
`oldest_acting_winners` (8.1, split into two — a Datasette canned query
is fixed SQL, no runtime ASC/DESC toggle), and `acting_wins_by_age_
bracket` (8.3).

Differences from the original outline: `metadata.yaml`'s canned
queries only accept literal inline SQL, not a reference to a file path
— so they couldn't "reference the `.sql` files from 5a" as originally
sketched; the SQL is copied in, adapted from the notebook cells
directly, not read from `queries/*.sql`. `category_history` uses
Datasette's own `:name` named-parameter style (vs. the CLI's positional
`?`) — Datasette renders a text-box input for it automatically.
Deliberately did **not** add `queries/person_history.sql` /
`title_search.sql` (the CLI's two lookups) as canned queries too: doing
so would mean a second, driftable copy of the same SQL, since
`metadata.yaml` can't reference the file directly. Ad-hoc lookups
inside Datasette's UI use its built-in "Execute SQL" box instead —
clean split preserved: CLI = parameterized lookups, Datasette = canned
reports.

Why Datasette over Flask/sql.js: zero code, native canned-query
support, Python-native, teaches the "introspect schema → auto-generate
UI" pattern. Free, local, no hosting needed. All 7 canned queries
verified against the notebook's own output (e.g. Titanic/LOTR tied at
11 wins each in `most_awarded_films`). Confirmed in practice:
`oscars.db` changes are reflected live (Datasette queries the file
fresh per request); `metadata.yaml` changes need a server restart (read
once at startup, not watched).

Tool: Claude Code (Sonnet).

### Phase 6 — Text-to-SQL LLM demo (Chat → Claude Code) — done

Prompt designed and eval-looped in Chat (Opus) per plan: `prompts/
system_prompt.txt` (v0.8), iterated over all 11 original test cases +
4 stretch cases from `phase6_notes.md` against `phase6_prompt_log.md`'s
eval log — schema context, data-scale summary, rule clusters for
category hierarchy / identifying films & people / JOIN paths /
answering behavior, safety constraints, output format. 7 fix rounds
(v0.1 → v0.8), each triggered by a concrete eval failure, not
speculative hardening; full changelog + per-case SQL/result/verdict is
in `phase6_prompt_log.md`.

Wiring built as `src/text_to_sql.py`: argument parsing (manual
`sys.argv`, matching `src/query.py`'s convention, no argparse), schema +
prompt assembly, API call, regex SQL-block extraction, a validator
(SELECT/WITH-only, single-statement), then read-only execution against
`oscars.db` with pandas output.

Differences from the original sketch:
- **Gateway is CBORG, not direct Anthropic.** The plan specified
  `ANTHROPIC_API_KEY` against `api.anthropic.com`; built against CBORG
  (LBNL's LiteLLM proxy, `https://api.cborg.lbl.gov`) instead, reading
  `CBORG_API_KEY`. The `anthropic` Python SDK works unmodified — only
  `base_url`/`api_key` differ — so the planned dependency didn't change.
  Full config recorded in `phase6_notes.md`'s "CBORG configuration"
  section (added after this was rediscovered from scratch twice across
  session restarts).
- **`--model NAME` flag**, not in the original plan. Needed because
  CBORG meters commercial Claude calls against a $50/month budget
  (~85% spent by the time this was wired in); the flag lets eval runs
  target CBORG's free `lbl/*`-prefixed on-prem models (`lbl/cborg-chat`
  etc.) and reserves commercial calls for real use. Default stays
  `claude-sonnet-5`.
- **No `--explain` flag.** The plan floated one as optional polish; not
  needed — the script shows the generated SQL by default, with
  `--quiet` to suppress it instead of a flag to opt in.
- **Missing SQL block is a designed refusal, not an error** — the plan's
  Part 3/response-format section originally treated "no code block
  found" as an error case; corrected once the eval log's stretch case 1
  (an intentionally unanswerable question) confirmed the prompt's
  refusal path is meant to reach the user as plain explanation text,
  exit 0, not an error message. `phase6_notes.md` updated to match.
- **Zero-row handling is aggregate-shape-dependent**, not something the
  code fully controls: a `COUNT()`-style question (e.g. "how many
  Oscars did Pixar win?") still returns one row valued `0`, printed
  normally; the script's dedicated "0 rows." + explanation path only
  fires for a plain `SELECT` that returns no rows at all. Both shapes
  verified working end-to-end.

Verified end-to-end (2026-08-06, via `--model lbl/cborg-chat`, $0 cost —
confirmed no change in CBORG spend across the run): normal ranked query,
the Japanese-films refusal case, a true zero-row case, and a CTE
(`WITH`) query all behaved as designed; `CBORG_API_KEY` unset fails
fast with a clear message before any API call.

Tool: Claude Chat (Opus) for prompt design, Claude Code (Sonnet) for
implementation and the CBORG migration.

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
