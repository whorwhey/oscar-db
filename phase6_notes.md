# Phase 6 Notes — Text-to-SQL LLM Demo

Design notes and reference for `src/text_to_sql.py`. Originally written
as the spec before building Phase 6; kept afterward for the sections
that are still load-bearing (the CBORG configuration below) and as a
record of what was decided and why.

Depended on: Phase 5a queries (proven, in `queries/*.sql`), Phase 5b CLI
(`src/query.py`), working `oscars.db`.

## Goal

A Python script that takes a natural-language question about Oscar
history, sends it (with schema context) to Claude's API, receives SQL
back, executes it against `oscars.db`, and prints formatted results.

This is a learning demo, not a product. The priorities are:
1. Learn prompt engineering for structured output (SQL)
2. Learn the Anthropic Python SDK
3. Produce something that works well enough to be satisfying

## Architecture

Single file: `src/text_to_sql.py`. No web framework, no database
abstraction layer. Thin pipeline:

```
user question (string)
  → prompt assembly (schema context + question + instructions)
    → CBORG API call (Claude model, via LBNL's gateway — see "CBORG
      configuration" below; not a direct api.anthropic.com call)
      → SQL extraction from response
        → execute against oscars.db (read-only)
          → format + print results (pandas or plain)
```

Dependencies to add: `anthropic` (Python SDK) — still the right SDK;
CBORG is Anthropic-API-compatible, so only the `base_url`/`api_key`
change, not the client library. Everything else (`sqlite3`, `pandas`)
is already available.

### Key design choice: stateless

Each invocation is independent. No conversation history, no follow-up
questions. The LLM sees the schema, the question, and nothing else.
This keeps the prompt predictable and testable.

If we want multi-turn later, that's a separate extension — not part of
the initial build.

## Prompt design

This section is the core of Phase 6. The prompt sent to the API has
three parts: schema context, database-specific rules, and the user's
question.

### Part 1: Schema context

Include the full `schema.sql` DDL verbatim. It's ~60 lines — small
enough that trimming it would lose information without meaningful token
savings. The DDL already has inline comments explaining each column.

Additionally, include a compact summary of actual data scale and
coverage so the LLM knows what's populated:

```
ceremonies: 98 rows (1st–98th, years 1927/28–2025)
categories: 66 rows, hierarchy: source_name → award_group (37) → class (8)
films: 5,265 rows; title_zh filled for ~1,324
people: 11,144 (10,836 persons + 308 companies)
nominations: 12,137
film_directors: 6,400 links (5,189 films → 3,213 directors)
```

### Part 2: Database-specific rules

These are the traps we've already learned building the database. Every
one of them caused a bug or confusion during Phase 5a query writing.
They go in the system prompt so the LLM doesn't repeat our mistakes.

**Film titles are NOT unique.** Two different films are named "Titanic"
(1953, 1997). Always GROUP BY / JOIN on `film_id`, never on `title`
alone. When displaying results, include `release_year` to disambiguate.

**Category hierarchy matters.** Don't filter on `source_name` unless the
user asks for a specific historical category name. Default behavior:
- General questions ("acting awards") → filter on `class`
- Specific questions ("Best Picture") → filter on `award_group`
- Historical questions ("what was SOUND RECORDING?") → use `source_name`
  or `raw_category`

Trap: `class = 'Directing'` sweeps in `ASSISTANT DIRECTOR`, a defunct
unrelated category. For directing questions, use
`award_group = 'Directing'` instead.

Trap: `award_group = 'Writing'` groups Adapted Screenplay, Original
Screenplay, Original Story, and Title Writing together. To distinguish
adapted from original, drop to `source_name`.

**Companies are in the `people` table.** `kind = 'company'` for 308
organizations (early Best Picture went to studios; Sci-Tech awards go
to firms). Filter `kind = 'person'` when the question is about
individuals, unless the question specifically asks about studios or
companies.

**`death_year IS NULL` is ambiguous.** It means unknown OR still alive.
Don't infer "alive" from NULL. If the question is about living people,
note this caveat in the output.

**Chinese title display uses COALESCE.** `title_zh` is NULL for ~75% of
films (expected, not missing). Display as:
`COALESCE(title_zh, title) AS display_title`
Same for people: `COALESCE(name_zh, name) AS display_name`

**Honorary/Sci-Tech awards often have no film.** A nomination with no
row in `nomination_films` is by design (citation-based awards), not
missing data. Don't INNER JOIN `nomination_films` when the question
could involve these categories — use LEFT JOIN or be aware the join
filters them out.

**Directors are in `film_directors`, not derived from nominations.**
A director who was never personally nominated still has rows in
`film_directors`. Use that junction table for "who directed X"
questions, not the nominations chain.

**`is_winner` is INTEGER 0/1**, not boolean. Use `is_winner = 1` for
winners, not `is_winner = TRUE`.

### Part 3: The user question

Passed verbatim as the final user message. No rewriting or
preprocessing on our side — let the LLM interpret it.

### Response format instruction

Ask the LLM to respond with:
1. The SQL query in a ```sql code block
2. A brief explanation of what the query does and why it's structured
   that way

Extract the SQL from the code block programmatically (regex or string
parsing). If no code block is found, that's the designed refusal path
(the prompt tells the model to emit no SQL when a question is
unanswerable from this schema) — print the model's explanation text and
exit 0, not an error. Confirmed working as intended: stretch case 1 in
`phase6_prompt_log.md`'s eval log.

### Safety constraints

Include in the system prompt:
- Generate SELECT statements only. Never INSERT, UPDATE, DELETE, DROP,
  ALTER, or any other mutation.
- Do not use `ATTACH DATABASE` or any pragma that modifies state.
- If the question cannot be answered from this schema, say so rather
  than guessing.

Enforce in code:
- Before executing, check that the SQL starts with SELECT (after
  stripping whitespace and comments). Refuse to execute anything else.
- Open the database connection as read-only:
  `sqlite3.connect('file:oscars.db?mode=ro', uri=True)`

## Known ambiguity patterns

These are questions where the LLM needs to make a judgment call.
Document them so we can evaluate whether its choices are reasonable.

- **"Who won Best Picture?"** — all-time or most recent? Default to
  all-time; if the user means a specific year they'll say so.
- **"Meryl Streep's nominations"** — person search by name. Should work
  with exact or close matches via LIKE. But: name collisions exist in
  the database (multiple people named "John Williams"). The LLM should
  include `person_id` or `birth_year` in output when results could be
  ambiguous.
- **"Movies about war"** — not answerable from this schema (no genre or
  plot data). The LLM should say so.
- **"Chinese title for Parasite"** — straightforward COALESCE query, but
  the film must be found by English title first.

## Evaluation

Phase 5a produced 12+ proven queries with known-correct results. Use
these as ground truth:

For each query, formulate the natural-language question it answers, feed
it to `text_to_sql.py`, and compare:
1. Does the generated SQL return the same result set?
2. If not, is the difference a legitimate alternative approach or a bug?

### Test cases (mapped from Phase 5a query list)

| # | Natural-language question | Phase 5a query | Key SQL concepts tested |
|---|---|---|---|
| 1 | List all Oscar ceremonies | query 1 | Basic SELECT, ORDER BY |
| 2 | Who won Best Picture in 2023? | query 2 | WHERE, JOIN, year interpretation |
| 3 | All nominations for Steven Spielberg | query 3 | Multi-table JOIN, person lookup |
| 4 | Which films won the most Oscars? | query 4 | GROUP BY, COUNT, ORDER BY |
| 5 | Most-nominated people who never won | query 5 | Subquery or LEFT JOIN anti-pattern |
| 6 | Search for person named "Stewart" | query 6 | LIKE, disambiguation |
| 7 | Search for films titled "Titanic" | query 7 | LIKE, duplicate titles |
| 8 | Who has the most wins across categories? | query 8 | Aggregate + JOIN |
| 9 | Best Picture winners whose director was never nominated for Directing | query 9 | Multi-join, category hierarchy |
| 10 | How has the Cinematography category name changed over the years? | query 10 | raw_category history |
| 11 | Youngest Best Actress winner | query 11 | Arithmetic, IS NOT NULL |
| 12 | Show Chinese titles for 2019 Best Picture nominees | query 12 | COALESCE display pattern |

### Stretch test cases (not in Phase 5a)

- "Which directors have won Best Picture but were never nominated for
  Directing?" (variant of 9 — tests whether the LLM picks
  `film_directors` + `award_group` correctly)
- "How many Oscars did Pixar win?" (tests `kind = 'company'` awareness)
- "What's the longest Best Picture winner?" (tests `runtime_minutes`)
- "Show me all Japanese films that won an Oscar" (tests
  `original_title` or lack of country data — should note limitation)

## Build sequence

1. **Prompt design session** (Chat, Opus) — finalize the system prompt
   text, test it by hand against 3–4 questions, iterate. Output: the
   prompt template as a string ready to paste into code.
2. **Scaffold** (Claude Code, Sonnet) — `src/text_to_sql.py` with:
   argument parsing, schema loading, prompt assembly, API call, SQL
   extraction, execution, output formatting. Get one end-to-end query
   working.
3. **Eval loop** (Claude Code or manual) — run all 12 test cases,
   compare results, tune the prompt rules based on failures.
4. **Polish** — error handling, help text. As built: the SQL is shown
   by default before executing (no `--explain` flag needed); `--quiet`
   suppresses it instead. A `--model NAME` flag overrides the default
   model.

## Files the Code agent needs

- `schema.sql` — the DDL, included verbatim in the LLM prompt
- `queries/*.sql` — proven queries for evaluation comparison
- `src/query.py` — existing CLI runner (reference for db connection
  patterns, output formatting)
- `oscars.db` — the database itself
- This file (`phase6_notes.md`) — the spec

## Dependencies

```
uv add anthropic
```

API key: set as `CBORG_API_KEY` environment variable (not
`ANTHROPIC_API_KEY` — see "CBORG configuration" below for why). Do not
hardcode. The script fails with a clear message before any API call if
the key is missing.

## CBORG configuration (as built)

Confirmed working 2026-08-06. Recorded here because this has been
re-derived from scratch after session restarts twice already — read
this section first next time, don't rediscover it.

- **Gateway:** CBORG, LBNL's LiteLLM proxy — not a direct
  `api.anthropic.com` call. Config lives in `src/text_to_sql.py` as
  module-level constants `CBORG_BASE_URL` and `DEFAULT_MODEL`.
- **Env var:** `CBORG_API_KEY`. `ANTHROPIC_API_KEY` is unset in this
  environment and unused by the script.
- **Base URL:** `https://api.cborg.lbl.gov`
- **SDK:** the `anthropic` Python SDK works unmodified against CBORG —
  `anthropic.Anthropic(api_key=<CBORG_API_KEY>, base_url=CBORG_BASE_URL)`.
  Confirmed by direct test; no need for the `openai` SDK (not installed
  in this project) even though CBORG also exposes an OpenAI-compatible
  surface.
- **Default model:** `claude-sonnet-5` — a bare CBORG alias, confirmed
  present in `GET /v1/models`. Coincidentally identical to the direct-
  Anthropic model string, but it's a CBORG-specific routing name (also
  available prefixed, e.g. `anthropic/claude-sonnet`, `google/claude-
  sonnet-5`), not guaranteed to stay aligned with Anthropic's own naming.
- **Free on-prem alternatives for eval runs** (don't count against the
  commercial budget): `lbl/cborg-chat` (confirmed working via the
  Anthropic SDK — backed by Gemma 4; needs `max_tokens` comfortably
  above ~200 or its reasoning burns the whole budget with empty visible
  `content`), plus `lbl/cborg-coder`, `lbl/cborg-mini`, `lbl/gpt-oss-20b`
  and others under the `lbl/` prefix. Select any of these with
  `--model NAME`.
- **Budget:** $50/month, resets the 1st (`budget_duration: "1mo"`, per
  `GET /user/info`). $42.64 spent as of 2026-07-27 — use the free
  `lbl/*` models for eval loops and prompt iteration; reserve commercial
  Claude calls for real use until the reset.

## What this is NOT

- Not a chatbot. No conversation history, no follow-ups.
- Not a web app. CLI only, same as `query.py`.
- Not production code. No retry logic, no rate limiting, no caching.
- Not trying to handle every possible question. The 12 test cases
  define the scope; anything beyond them is bonus.
