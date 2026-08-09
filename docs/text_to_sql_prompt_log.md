# Text-to-SQL System Prompt — Changelog & Eval Log

**Status:** v0.8 extracted to `prompts/system_prompt.txt` and wired into
`src/text_to_sql.py`. This file is now changelog + eval log only — the
prompt text itself lives in the extracted file, not here.

**Version:** v0.8 (2026-08-05)

Companion to `docs/text_to_sql.md`. Where the two disagree, this file
wins — `docs/text_to_sql.md` was written before the schema probe.

---

## Changelog

**v0.1** — assembled in Chat (Opus). Schema context, data summary,
4 rule clusters, output format, safety.

**v0.2** — two fixes from eval case 9:
- *Cluster C:* new rule on `film_directors` coverage gaps. Case 9's query
  INNER JOINed `film_directors` and silently dropped `Wings` (1927/28), the
  only Best Picture winner with no director row. Same bug class as the
  `nomination_films` rule that already existed.
- *Cluster B:* narrowed the Best Picture / `kind` rule. It read as a blanket
  instruction attached to "Best Picture questions" and could suppress
  `kind = 'person'` where it was genuinely needed. Now scoped to the nominee
  case with the mechanism stated.

**v0.3** — two fixes, from eval cases 2 and 10:
- *Cluster B:* the v0.2 kind-filter rule's own trigger phrase ("who
  *received* a Best Picture award") was close enough to the plain "who won
  Best Picture" question shape that it pulled the model into a
  `nomination_people`-based query for a question the established ground
  truth (notebook cell 23-equivalent) answers with a plain film lookup —
  3 rows of producers instead of 1 row naming the film. Split the rule in
  two: a new sentence states the film-level default ("who won X" →
  nomination_films, not people) and scopes the existing kind-filter
  caution to only fire once the model has already decided, for other
  reasons, to query people.
- *Cluster A (category hierarchy):* case 10 found that filtering to a
  single literal `source_name` for a "how has category X's name changed"
  question silently drops sibling `source_name` rows that are historical
  splits of the same `award_group` (e.g. Cinematography's 1939–1966
  Black-and-White/Color split) — and that the old rule 1 and rule 3 could
  give conflicting guidance on the same question. Rewrote rule 3 to
  require `award_group` + `GROUP BY raw_category` for "changed over time"
  questions, added rule 4 for the genuinely-narrow single-variant case,
  and added a TRAP naming the other award_groups with the same split
  shape.

**v0.4** — one fix from eval case 3:
- *Cluster B:* the existing LIKE rule's own example (`'%Day-Lewis%'`) is
  surname-only, and nothing in the prompt warned against that pattern for
  a full name. "All nominations for Steven Spielberg" generated
  `p.name LIKE '%Spielberg%'`, which also matched Anne Spielberg (his
  sister, a separate person row) — a real family-collision, not a
  hypothetical: this database also has 4 Coppolas and 5 Hustons. Added a
  TRAP requiring a full-name pattern (wildcard between parts) whenever the
  question gives a full name, reserving surname-only for when that's
  literally all the question gives.

**v0.5** — consolidation pass, correcting rather than adding. v0.2–v0.4 each
patched a specific case without checking whether the fix contradicted
existing text; this pass re-verified every factual claim and example in the
prompt against `oscars.db` directly and corrected what didn't hold:
- The LIKE example (`'%Day-Lewis%'`) directly contradicted the surname-only
  TRAP added right below it in v0.4. Replaced with `'%Daniel%Day-Lewis%'`.
- Hierarchy rule 1 used "Best Actress" as an award_group example — no such
  string exists among the 37 (the real value is `Actress -- Leading Role`).
  Replaced the example list and added a verified colloquial → award_group
  mapping for the 8 most likely colloquial asks (Best Actor/Actress/
  Supporting Actor/Supporting Actress/Director/Picture/Original Song/Score).
- The Cinematography TRAP (v0.3) said "filter award_group"; the Writing
  TRAP (v0.1) said "filter source_name" — direct contradiction, both
  presented as unconditional. Queried every award_group with more than one
  source_name and their ceremony ranges to find the actual discriminator:
  whether the source_name variants are chronologically exclusive remnants of
  one award (Cinematography's B&W/Color split, Costume Design and
  Production Design the same shape, Sound Mixing a clean rename) vs. two or
  more still-active-today source_names recognizing genuinely different work
  (Writing's Adapted vs. Original Screenplay, both awarded every year).
  Replaced both TRAPs with one rule stating this mechanism plus a default
  (prefer award_group) for the unsure case.
- The LIMIT rule's "order newest first" instruction had no scope condition,
  so it applied even to ranked results — which would have overwritten the
  `ORDER BY nomination_count DESC` / `win_count DESC` that cases 5 and 8
  actually needed. Restricted it to plain chronological lists.
- "include birth_year when available" softened a rule that should be
  unconditional — birth_year should always be selected, NULL or not, so the
  gap itself is visible. Tightened the wording.
- The "multiple John Williams" example was checked and is false: `oscars.db`
  has exactly one `John Williams` (person_id 2679). Verified `people` for an
  actual `kind = 'person'` name collision and replaced it with Chris
  Cooper (2 distinct person rows, different imdb_ids).
- Full-prompt audit against `oscars.db`: every remaining data-scale number,
  the full `class` (8) and `award_group` (37) lists, the Titanic/Wings/
  Assistant-Director/Best-Picture-studio claims, and the year_label
  examples all verified correct as written — no further changes.
- Method section: added a requirement that the eval log capture the
  model's explanation text, not just its SQL and result set — the output
  format asks the model to state its hierarchy choice and ambiguity
  handling, and nothing in the log so far has actually recorded whether
  that happens.

**v0.6** — one fix from eval case 11:
- *Cluster C (JOIN paths):* "youngest Best Actress winner," a plain
  ranking query with no COUNT, listed Janet Gaynor three times — her sole
  win (1st ceremony) is one nomination linked to three films (7th Heaven,
  Sunrise, Street Angel), a body-of-work citation style used only in
  ceremonies 1–3 and 8 (18 nominations total, verified against
  `nomination_films`). The existing "Counting" rule only warned about
  `COUNT(*)` after a junction-table JOIN; it didn't cover the same
  fan-out corrupting a plain listing/ranking query. Added a rule stating
  the mechanism and the fix (DISTINCT on person_id/nomination_id).

**v0.7** — one fix from eval case 1:
- *Cluster D (answering behavior):* the v0.5 consolidation pass's own
  LIMIT/ordering rewrite had an oversight — "list all Oscar ceremonies"
  triggered its "plain chronological list → newest first" clause even
  though no LIMIT applied (the user asked for "all", so nothing was
  truncated), producing all 98 ceremonies ordered 98 → 1. The notebook's
  ground truth for the equivalent question (1.1, "oldest first") orders
  ascending. Newest-first only serves a purpose when a LIMIT is actually
  cutting the list short so the visible rows should be the recent ones;
  forcing it on a complete, untruncated result has no such justification.
  Split the rule so DESC only applies when a LIMIT is truncating the list;
  a complete result orders ascending instead.

**v0.8** — one fix from the stretch case "How many Oscars did Pixar win?":
- *Cluster B (identifying films and people):* the existing kind = 'company'
  rule implies studio-level questions are generally answerable this way,
  but Pixar has zero matching rows — confirmed the query executes cleanly
  and returns `0`, a confidently-wrong-looking answer given Pixar's films
  have many real wins (Finding Nemo, The Incredibles, Ratatouille, Up,
  Brave, Inside Out, Coco, Soul all won Animated Feature and more, sampled
  directly). Checked how general this is: Warner Bros. and Disney do have
  rows (multiple historical name variants, from their Best-Picture-era
  studio credits); Marvel and Netflix, like Pixar, have none. `kind =
  'company'` coverage is essentially early-Hollywood-era plus a few
  Sci-Tech technology firms, not a general studio index. Added a TRAP
  stating this and requiring the model to say so rather than reporting a
  bare zero when a company search comes up empty.

---

## The system prompt

The prompt text lives in `prompts/system_prompt.txt` (v0.8, matching the
eval log below). `{schema_sql}` is a placeholder — `src/text_to_sql.py`
reads `schema.sql` from disk at runtime and substitutes it in.

---

## Eval log

### Case 9 — PASS (with two fixes)

**Question:** Best Picture winners whose director was never nominated for
Directing.

**Note:** `docs/text_to_sql.md` maps this to Phase 5a query 9, but that
query was never built. No ground truth — verified by hand.

**Result:** 5 rows — CODA (Sian Heder), Green Book (Peter Farrelly), Argo
(Ben Affleck), Slumdog Millionaire (Loveleen Tandan), Grand Hotel (Edmund
Goulding). Against 98 total Best Picture winners. All five verified correct.

**Rules exercised:** `award_group = 'Directing'` not `class` (Assistant
Director trap); `film_directors` as the director source; `NOT IN` subquery
across all ceremonies; disambiguating columns included unasked.

**Gap found → fixed in v0.2:** INNER JOIN to `film_directors` dropped Wings.

**Gap found → fixed in v0.2:** Best Picture / `kind` rule was too broad.

**Open ambiguity, not fixed:** "never nominated for Directing" — ever, or not
for *that film*? The query took "ever." Under the other reading, Driving Miss
Daisy (Bruce Beresford, snubbed 1989 but nominated for Tender Mercies in
1983) would appear and does not. Both readings are defensible. A rule for
negation scope is probably too question-specific to be worth adding, but the
output format already asks the model to state its interpretation — check
whether it actually does.

**Watch item:** the LIMIT rule says add `LIMIT 20` when a query "could return
hundreds of rows." No LIMIT was added here. Whether that threshold is applied
consistently is worth tracking across cases before making it explicit.

---

### Case 12 — PASS

**Question:** Show Chinese titles for 2019 Best Picture nominees.

**Generated SQL:**
```sql
SELECT
    f.film_id,
    COALESCE(f.title_zh, f.title) AS display_title,
    f.release_year
FROM nominations n
JOIN categories cat ON cat.category_id = n.category_id
JOIN ceremonies cer ON cer.ceremony = n.ceremony
JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
JOIN films f ON f.film_id = nf.film_id
WHERE cat.award_group = 'Best Picture'
  AND cer.year_label = '2019'
ORDER BY f.title;
```

**Result:** 9 rows (the 2019 Best Picture nominee slate: 1917, 极速车王,
乔乔的异想世界, 小丑, 小妇人, 婚姻故事, 好莱坞往事, 寄生虫, 爱尔兰人).
One film (1917) has no `title_zh` and correctly falls back to its English
title via `COALESCE`.

**Rules exercised:** `award_group = 'Best Picture'` (named award →
award_group level); `year_label` interpreted as eligibility year, not
ceremony-held year; `COALESCE(title_zh, title)` applied because the
question is specifically about Chinese titles; `release_year` included
per the disambiguation rule even though not asked; INNER JOIN to
`nomination_films` used because the question is clearly about films (safe
here — Best Picture nominees always have a film row).

**Compare:** Matches notebook 8.2 exactly — same join chain
(`films → nomination_films → nominations → categories`, plus
`ceremonies`), same `WHERE`, same `COALESCE`. Same result set. Pass.

**Gaps found:** none.

---

### Case 5 — PASS

**Question:** Most-nominated people who never won.

**Generated SQL:**
```sql
SELECT
    p.person_id,
    p.name,
    p.birth_year,
    COUNT(*) AS nomination_count
FROM people p
JOIN nomination_people np ON np.person_id = p.person_id
JOIN nominations n ON n.nomination_id = np.nomination_id
WHERE p.kind = 'person'
  AND p.person_id NOT IN (
      SELECT np2.person_id
      FROM nomination_people np2
      JOIN nominations n2 ON n2.nomination_id = np2.nomination_id
      WHERE n2.is_winner = 1
  )
GROUP BY p.person_id
ORDER BY nomination_count DESC
LIMIT 20;
```

**Result:** 20 rows, top: Greg P. Russell (16), Thomas Newman (15), Roland
Anderson (15), George J. Folsey (14), Daniel Sudick (13), Bradley Cooper
(12) ... Katie Spencer (7).

**Rules exercised:** `kind = 'person'` (question is about individuals);
`person_id` + `birth_year` disambiguating columns included per rule;
`LIMIT 20` applied per the large-result-set rule ("most-nominated" implies
a ranked top-N, could otherwise return ~thousands of rows); no
`COUNT(DISTINCT)` needed — grouping by `person_id` already scopes
`COUNT(*)` to that person's `(nomination_id, person_id)` rows, which the
junction table's PK guarantees are already deduplicated.

**Compare:** Notebook 4.2 asks the identical question, using
`HAVING SUM(is_winner) = 0` instead of the anti-join `NOT IN`. Ran both —
identical top-10 names, counts, and order. Same result set via a
legitimate alternative formulation. Pass.

**Gaps found:** none.

---

### Case 8 — FAIL (ambiguity, not a prompt bug)

**Question:** Who has the most wins across categories?

**Generated SQL:**
```sql
SELECT
    p.person_id,
    p.name,
    p.birth_year,
    COUNT(DISTINCT n.nomination_id) AS win_count
FROM people p
JOIN nomination_people np ON np.person_id = p.person_id
JOIN nominations n ON n.nomination_id = np.nomination_id
WHERE p.kind = 'person'
  AND n.is_winner = 1
GROUP BY p.person_id
ORDER BY win_count DESC
LIMIT 20;
```

**Result:** 20 rows, top: Walt Disney (26), Douglas Shearer (14), Iain
Neil (13), Cedric Gibbons (11), Farciot Edouart (10) ...

**Rules exercised:** `kind = 'person'`; `COUNT(DISTINCT n.nomination_id)`
per the counting rule (not strictly required here since `nomination_people`'s
PK already prevents duplicate person-nomination pairs, but not wrong
either); `person_id` + `birth_year` disambiguation; `LIMIT 20`.

**Compare:** `docs/text_to_sql.md`'s mapped ground truth is notebook 4.3, "who
has won across the most different Oscar categories" — `COUNT(DISTINCT
category_id)` breadth, not total win count. Ran both: rank-1 agrees (Walt
Disney), but the rest diverges hard — e.g. Iain Neil ranks #3 by total
wins (13, nearly all in one Sci-Tech award_group repeated) but doesn't
appear in the top 10 by category breadth at all. Different questions,
different answers — this is not "same result set, different SQL."

**Verdict:** the question text itself is genuinely ambiguous between
"total win count" and "breadth across distinct categories" — nothing in
the schema or the prompt's rules resolves it, and a human reader would
need the same clarification. This is a question-phrasing problem, not a
database trap, so no rule added (would dilute the others per the
loop's own guidance). Logged as an open question instead.

**Open question:** should the output-format instruction be strengthened
to *require* the model to state which reading of an ambiguous aggregate
("most X" — total count vs. distinct-category breadth vs. per-category
max) it chose, whenever "across categories" / "across years" / similar
scope words appear in the question? The current instruction already asks
for this ("how you handled any ambiguity") but doesn't specifically flag
count-vs-breadth as a recurring ambiguity shape. Worth deciding after
seeing whether this pattern recurs (case 9's "never nominated — ever, or
for that film?" is the same shape: an aggregate/negation scope ambiguity
the prompt doesn't structurally address).

**Gaps found:** none added to the prompt this round.

---

### Case 2 — FAIL (fixed in v0.3)

**Question:** Who won Best Picture in 2023?

**Generated SQL (against v0.2):**
```sql
SELECT
    f.film_id,
    f.title,
    f.release_year,
    p.person_id,
    p.name,
    p.kind
FROM nominations n
JOIN categories cat        ON cat.category_id = n.category_id
JOIN ceremonies cer        ON cer.ceremony = n.ceremony
JOIN nomination_films nf   ON nf.nomination_id = n.nomination_id
JOIN films f                ON f.film_id = nf.film_id
JOIN nomination_people np  ON np.nomination_id = n.nomination_id
JOIN people p               ON p.person_id = np.person_id
WHERE cat.award_group = 'Best Picture'
  AND n.is_winner = 1
  AND cer.year_label = '2023'
ORDER BY p.name;
```

**Result:** 3 rows — Oppenheimer's three credited producers (Charles
Roven, Christopher Nolan, Emma Thomas), each row repeating the same film.

**Rules exercised:** `award_group = 'Best Picture'`; `year_label`
eligibility-year interpretation; `person_id` disambiguation; the v0.2
kind-filter rule (which is what pulled it toward `nomination_people` in
the first place — see gap below).

**Gap found → fixed in v0.3:** compared against the notebook's proven
pattern (cell 23, same query shape for year_label '2019', re-run here for
'2023' as ground truth) — 1 row, `('2023', 'Best Picture', 'Oppenheimer')`,
no people involved at all. The v0.2 rule's trigger phrasing ("who
*received* a Best Picture award") reads as directly matching "who won
Best Picture," so the model built a producers-centric query for a
question the established ground truth answers at the film level. Root
cause: the rule conflated two separate things — *when* to go
person/company-level, and *how* to filter kind once you're there. Split
in v0.3 (see changelog): default is film-level; person/company-level only
on explicit ask; the kind-filter caution now only applies once already
querying people.

**Open question:** re-test this case against v0.3 in a future pass to
confirm the split rule actually produces the 1-row film-level answer and
doesn't overcorrect into refusing legitimate producer-level questions
("who produced the film that won Best Picture in 2023?").

**Re-tested against v0.5:** yes. v0.5's consolidation pass rewrote this
same rule again (see v0.5 changelog), so it needed re-verification, not
just a rerun of the untouched v0.3 fix. Generated SQL:
```sql
SELECT c.year_label, cat.award_group, f.title, f.release_year
FROM nominations n
JOIN ceremonies c ON c.ceremony = n.ceremony
JOIN categories cat ON cat.category_id = n.category_id
JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
JOIN films f ON f.film_id = nf.film_id
WHERE n.is_winner = 1
  AND cat.award_group = 'Best Picture'
  AND c.year_label = '2023';
```
Result: 1 row — `('2023', 'Best Picture', 'Oppenheimer', 2023)`. Matches
the notebook-pattern ground truth exactly. Fix confirmed still working
after the v0.5 rewrite. The producer-level overcorrection question (a
hypothetical "who produced the film that won" ask) remains untested — out
of scope for this pass, which only re-verified the originally-failing
question.

---

### Case 10 — FAIL (fixed in v0.3)

**Question:** How has the Cinematography category name changed?

**Generated SQL (against v0.2, following rule 3 literally):**
```sql
SELECT n.raw_category, MIN(n.ceremony) AS first_ceremony, MAX(n.ceremony) AS last_ceremony, COUNT(*) AS times_used
FROM nominations n
JOIN categories cat ON cat.category_id = n.category_id
WHERE cat.source_name = 'CINEMATOGRAPHY'
GROUP BY n.raw_category
ORDER BY first_ceremony;
```

**Result:** 1 row — `CINEMATOGRAPHY`, ceremonies 1–98, 347 uses. Looks
complete (spans the full range) but isn't.

**Rules exercised:** v0.2 rule 3 ("historical/changed name → source_name"),
`MIN`/`MAX`/`COUNT` grouped on raw_category (matches the notebook 4.4
pattern for a different category).

**Gap found → fixed in v0.3:** `categories` has 3 source_name rows under
award_group = 'Cinematography' (`CINEMATOGRAPHY`, `CINEMATOGRAPHY
(Black-and-White)`, `CINEMATOGRAPHY (Color)`). Filtering to the single
literal source_name silently dropped the 27 ceremonies (12–39) where the
award was split into Black-and-White/Color — the 1-row, full-range-looking
result actively hid that the category was ever split, which is the
opposite of what "how has the name changed" is asking for. Re-ran filtered
on award_group = 'Cinematography' instead: 3 rows, correctly showing the
plain category (ceremonies 1–98) alongside the concurrent 1939–1966 split.
Root cause, and a second finding: v0.2 rule 1 ("names a specific award →
award_group") and rule 3 ("historical name change → source_name") actually
conflicted on this exact question, since "Cinematography" satisfies both
triggers — whichever rule the model leaned on determined right vs. wrong
by accident. Rewrote rule 3 to require award_group + GROUP BY raw_category
for "how has X changed" questions, added rule 4 for the genuinely-narrow
case (naming one exact historical variant), and added a TRAP naming the
other award_groups with the same split shape (Costume Design, Directing,
Sound Mixing, several Scientific and Technical / Special groups — see
case 5's award_group counts).

**Open question:** re-test against v0.3 to confirm rule 3/4 no longer
conflict with rule 1, and check a "what was SOUND RECORDING?" -style
question (the prompt's own rule-3 example) still resolves correctly under
the new rule 4 — SOUND RECORDING's source_name/award_group relationship
wasn't checked this round.

**Re-tested against v0.5:** yes — necessary since v0.5 replaced the
Cinematography TRAP entirely (merged with the Writing TRAP into a single
two-shape rule; see v0.5 changelog) and rule 1's own example set changed
too. Generated SQL, straight from rule 3's own worked example (the
question and the rule's example are now identical text):
```sql
SELECT n.raw_category, MIN(n.ceremony) AS first_ceremony, MAX(n.ceremony) AS last_ceremony, COUNT(*) AS times_used
FROM nominations n
JOIN categories cat ON cat.category_id = n.category_id
WHERE cat.award_group = 'Cinematography'
GROUP BY n.raw_category
ORDER BY first_ceremony;
```
Result: 3 rows — CINEMATOGRAPHY (ceremonies 1–98, 347 uses),
CINEMATOGRAPHY (Black-and-White) (12–39, 161), CINEMATOGRAPHY (Color)
(12–39, 135). Matches the corrected ground truth from the original v0.3
fix. Confirmed still working after the v0.5 rewrite. The SOUND RECORDING
open question from the v0.3 note remains untested — still out of scope,
not part of this pass's re-test target.

---

### Case 3 — FAIL (fixed in v0.4)

**Question:** All nominations for Steven Spielberg.

**Generated SQL (against v0.3):**
```sql
SELECT
    p.person_id,
    p.name,
    cer.year_label,
    cat.award_group,
    n.raw_category,
    n.is_winner,
    f.title,
    f.release_year
FROM people p
JOIN nomination_people np ON np.person_id = p.person_id
JOIN nominations n ON n.nomination_id = np.nomination_id
JOIN categories cat ON cat.category_id = n.category_id
JOIN ceremonies cer ON cer.ceremony = n.ceremony
LEFT JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
LEFT JOIN films f ON f.film_id = nf.film_id
WHERE p.name LIKE '%Spielberg%'
  AND p.kind = 'person'
ORDER BY cer.ceremony;
```

**Result:** 25 rows — 24 for Steven Spielberg (person_id 3510: Close
Encounters through Hamnet, including the 1986 Thalberg and the two
Schindler's List wins) plus **1 row for Anne Spielberg** (person_id 4715,
his sister, 1988 Writing nomination for Big) that should not be there.

**Rules exercised:** `LEFT JOIN` to `nomination_films`/`films` (question
spans all award types, correctly defensive even though Spielberg has no
filmless nominations in practice); `kind = 'person'`; the LIKE-not-`=`
rule. **Rule followed incompletely:** `birth_year` was not included
alongside `person_id` despite the existing disambiguation rule requiring
it when available — a generation-time miss, not a prompt gap (the rule
already states this clearly); noted, not fixed.

**Gap found → fixed in v0.4:** the LIKE pattern used only the surname
(`'%Spielberg%'`, mirroring the prompt's own `'%Day-Lewis%'` example),
which silently pulled in Anne Spielberg — a different, unrelated-to-the-
question person who happens to share the surname. Checked whether this is
a one-off: it isn't — this database has 4 Coppolas and 5 Hustons among
`kind = 'person'` rows, all real Hollywood families. Added a TRAP
requiring the full name (with a wildcard between parts) whenever the
question gives one.

**Stop condition reached:** this is the third case in a row (cases 2, 10,
3) that required a prompt change, per the loop's own stopping rule.
Stopping here rather than continuing to cases 7/6/11/4/1 — see report to
Francis below the log for what this pattern suggests about the prompt.

---

### Case 7 — PASS

**Question:** Search for films titled "Titanic".

**Generated SQL:**
```sql
SELECT film_id, title, release_year, imdb_id
FROM films
WHERE title LIKE '%Titanic%'
ORDER BY release_year;
```

**Generated explanation (per fix 8, now recorded):** "This is a title
lookup, not a category question, so no hierarchy level applies. I used
LIKE with wildcards per the name/title lookup rule, since users may not
match capitalization exactly. I included release_year and film_id because
film titles are not unique in this database — this prompt specifically
flags 'Titanic' as an example of two different films sharing a title
(1953 and 1997), so both need to surface distinctly rather than being
merged or arbitrarily picked."

**Result:** 2 rows — Titanic (1953, tt0046435), Titanic (1997, tt0120338).

**Rules exercised:** LIKE-not-`=`; film disambiguation (release_year,
film_id) for the exact Titanic case the prompt names by name; no LIMIT
needed (a single-title search can't plausibly return hundreds of rows).
Explanation correctly names the ambiguity it's resolving, satisfying the
output-format requirement — first direct confirmation of this since fix 8
started requiring the log to capture it.

**Compare:** Character-identical to notebook cell 13 (2.1). Pass.

**Gaps found:** none.

---

### Case 6 — FAIL (question-wording ambiguity, not a prompt bug)

**Question:** Search for person named "Stewart".

**Generated SQL:**
```sql
SELECT person_id, name, birth_year
FROM people
WHERE name LIKE '%Stewart%'
  AND kind = 'person'
ORDER BY name;
```

**Generated explanation:** "No category hierarchy applies — this is a
name lookup. 'Stewart' is a surname given with no first name, so per the
surname-only TRAP's carve-out (that's literally all the question gives), a
surname-only LIKE pattern is appropriate here rather than a false trap
trigger. The question says 'person', so I filtered kind = 'person' to
exclude companies. Included person_id and birth_year since person names
collide in this database."

**Result:** 17 rows, including two real same-surname collisions worth
flagging on their own — James Stewart (547, 1908–1997, the actor) vs.
James G. Stewart (885, 1907–1997, a different, separately-credited person)
— exactly the kind of collision the disambiguation rule exists for.

**Rules exercised:** surname-only LIKE correctly applied under its own
carve-out; `kind = 'person'` per the question's explicit wording;
`person_id` + `birth_year` disambiguation.

**Compare:** notebook 2.2 asks a differently-worded question — "which
**people** in the database have 'Stewart' somewhere in their name?" — with
no `kind` filter at all, 18 rows. Re-ran without the kind filter: the
18th row is `Stewart Filmscreen Corporation` (person_id 2487, kind =
'company'), which my query correctly excludes under its own question but
the notebook's differently-scoped question includes. Not the same result
set — but not a prompt bug either: the eval's test-case wording ("person")
and the notebook's original wording ("people") genuinely ask different
things, and the kind rule fired exactly as designed for the question it
was actually given. Logged as a wording-ambiguity finding, not a rule
gap — the discrepancy is between this eval's phrasing and the notebook's
phrasing, not between the prompt's rules.

**Aside, unrelated to the prompt:** `ROY C. STEWART AND SONS` (person_id
1925) is classified `kind = 'person'` despite being obviously a business
name ("AND SONS") — a pre-existing data-quality gap in the underlying
`kind` classification (see docs/project_history.md's history of similar
id-less-company reclassification passes), not something a text-to-SQL
prompt rule could catch or should try to.

**Gaps found:** none.

---

### Case 11 — FAIL (fixed in v0.6)

**Question:** Youngest Best Actress winner.

**Generated SQL (against v0.5):**
```sql
SELECT
    p.person_id,
    p.name,
    p.birth_year,
    f.title,
    f.release_year,
    (f.release_year - p.birth_year) AS approx_age_at_win
FROM nominations n
JOIN categories cat ON cat.category_id = n.category_id
JOIN nomination_people np ON np.nomination_id = n.nomination_id
JOIN people p ON p.person_id = np.person_id
JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
JOIN films f ON f.film_id = nf.film_id
WHERE n.is_winner = 1
  AND cat.award_group = 'Actress -- Leading Role'
  AND p.birth_year IS NOT NULL
ORDER BY approx_age_at_win ASC
LIMIT 5;
```

**Generated explanation:** "'Best Actress' is colloquial, mapped per rule
1 to award_group = 'Actress -- Leading Role'. I computed age as
release_year minus birth_year and filtered birth_year IS NOT NULL first,
since NULL arithmetic would otherwise produce unpredictable ordering. I
used LIMIT 5 to show the youngest few for context rather than just one,
in case of near-ties."

**Result (against v0.5):** top rows — Janet Gaynor (age 21, 7th Heaven,
1927) — **three times**, once per film — then Marlee Matlin (21, 1986)
sitting between two of the Gaynor rows.

**Rules exercised:** the new colloquial mapping from this pass's fix 2
(Best Actress → `Actress -- Leading Role`) worked correctly; NULL-guarding
birth_year before arithmetic; disambiguating columns.

**Gap found → fixed in v0.6:** a nomination can link to more than one
film — 18 nominations do (verified via `nomination_films` GROUP BY),
concentrated in ceremonies 1–3 and 8, a body-of-work citation style from
the era before one-film-per-nomination became standard. Janet Gaynor's
single win at the 1st ceremony cites three films at once. The prompt's
existing "Counting" rule only addressed `COUNT(*)` after this kind of
join; nothing warned that a plain, non-aggregate ranking query has the
same duplication problem. Added a rule in v0.6 (see changelog) covering
the mechanism and the fix.

**Open question:** re-test this case against v0.6 in a future pass to
confirm DISTINCT actually collapses Janet Gaynor to one row without
dropping the real second-place tie (Marlee Matlin, also 21).

---

### Case 4 — PASS

**Question:** Which films won the most Oscars?

**Generated SQL:**
```sql
SELECT
    f.film_id,
    f.title,
    f.release_year,
    COUNT(*) AS wins
FROM nominations n
JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
JOIN films f ON f.film_id = nf.film_id
WHERE n.is_winner = 1
GROUP BY f.film_id
ORDER BY wins DESC
LIMIT 20;
```

**Generated explanation:** "No category hierarchy filter applies — the
question spans all award types. I used INNER JOIN to nomination_films
since the question is fundamentally about films (the JOIN PATHS rule's
carve-out for that). COUNT(*) here counts wins correctly rather than
needing DISTINCT, since each nomination_films row already represents one
distinct win credited to that film — including cases where one win
nomination credits multiple films, which correctly gives each of those
films credit for that win. Grouped on film_id, not title, since titles
collide. LIMIT 20 with the ranking intact, per the LIMIT rule's
ranked-result carve-out."

**Result:** top 3 tied at 11 wins — The Lord of the Rings: The Return of
the King (2003), Titanic (1997), Ben-Hur (1959) — then West Side Story and
Gone with the Wind at 10.

**Rules exercised:** INNER JOIN correctly chosen for a films-are-the-point
question; GROUP BY film_id not title; LIMIT + ranked ORDER BY preserved
(the v0.5 LIMIT fix working as intended); explanation correctly reasons
through why the nomination_films fan-out is *wanted* here rather than a
bug (contrast with case 11, where the same fan-out was a bug because the
question was about winners, not wins-per-film).

**Compare:** Matches notebook 4.1 exactly in structure (same joins, same
WHERE/GROUP BY/ORDER BY). Ran notebook's LIMIT 10 version — identical top
10 films and counts, in the same order, as the first 10 rows of my LIMIT
20. Pass.

**Gaps found:** none.

---

### Case 1 — FAIL (fixed in v0.7)

**Question:** List all Oscar ceremonies.

**Generated SQL (against v0.6):**
```sql
SELECT ceremony, year_label
FROM ceremonies
ORDER BY ceremony DESC;
```

**Generated explanation:** "No LIMIT applied — the question asks for
'all' ceremonies explicitly, and the LIMIT rule only fires when the user
did not ask for everything. This is a plain chronological list with no
ranking metric, so per that same rule I ordered newest first."

**Result:** all 98 rows, ceremony 98 (2025) through ceremony 1 (1927/28).

**Rules exercised:** the "user asked for all, don't LIMIT" condition
correctly suppressed LIMIT despite 98 being a sizeable table; the plain-
chronological-list ordering clause fired as written.

**Gap found → fixed in v0.7:** compared against notebook 1.1, whose actual
question is "what are all 98 Oscar ceremonies, **oldest first**?" — `ORDER
BY ceremony` ascending, no DESC. Same 98 rows, opposite order. Root cause:
this pass's own v0.5 LIMIT-rule rewrite (see changelog) added the newest-
first clause to serve truncated lists — so the visible rows are the recent
ones — but wrote the trigger as "a plain chronological list ('list all
X')" without conditioning it on whether a LIMIT is actually cutting
anything. Since this case's LIMIT was correctly suppressed (the user
asked for all), nothing was being truncated, so forcing DESC had no
purpose and produced a non-canonical order. Fixed in v0.7 by tying
newest-first specifically to the truncating case; a complete result now
orders ascending.

This is the last of the 11 original cases — see the end-of-run report for
what to do next.

---

### Stretch 1 — PASS (weak test — see caveat)

**Question:** Show me all Japanese films that won an Oscar.

**Generated response (no SQL emitted):** "This database has no country or
language data — `films` tracks title, imdb_id, release_year,
original_title, and runtime_minutes only, nothing indicating national
origin or production language. I can't identify 'Japanese films' from
this schema. Guessing from `original_title` (e.g. treating a non-English
original title as a signal of Japanese origin) would be an unreliable
proxy — a non-English original title could belong to a film from any
non-English-speaking country, not specifically Japan — so I'm not
attempting it. No SQL query follows."

**Judged on both required parts:**
- **No SQL block emitted:** yes.
- **Names the missing data specifically:** yes — "no country or language
  data," not a vague "I can't help with that."
- **No proxy substitution:** yes — explicitly declines to guess from
  `original_title` and states why that proxy would be unreliable, not just
  that it's unavailable.

**Verified against `schema.sql`:** `films` has exactly 8 columns (film_id,
title, title_zh, imdb_id, douban_id, release_year, original_title,
runtime_minutes) — no country or language column exists anywhere in the
schema. The refusal is factually correct, not just well-phrased.

**Caveat, per the instruction to weight this test accordingly:** this
question is nearly verbatim the prompt's own worked example in the
ANSWERING BEHAVIOR section ("'show me Japanese films that won' are not
answerable — do not substitute a proxy such as guessing nationality from
original_title"). A model that pattern-matches the literal example text
would pass this without demonstrating it can generalize refusal to a
differently-worded unanswerable question (e.g. "which winners were shot in
France?" or "how many silent films won?" — no such column either, but
neither is name-checked in the prompt). This is the only refusal test in
the suite, so a pass here is weaker evidence of general refusal competence
than a pass on a case with no matching worked example. Flagging as an open
question rather than a gap, since adding more refusal examples risks
prompt sprawl for a behavior that's already stated as a general principle
("If the schema cannot answer the question, say so plainly... and name the
missing data"), not just tied to this one example.

**Gaps found:** none.

---

### Stretch 2 — FAIL (fixed in v0.8)

**Question:** How many Oscars did Pixar win?

**Generated SQL (against v0.7):**
```sql
SELECT COUNT(DISTINCT n.nomination_id) AS oscar_wins
FROM nominations n
JOIN nomination_people np ON np.nomination_id = n.nomination_id
JOIN people p ON p.person_id = np.person_id
WHERE n.is_winner = 1
  AND p.name LIKE '%Pixar%'
  AND p.kind = 'company';
```

**Generated explanation:** "'Pixar' is a company, so per the kind rule I
filtered kind = 'company' rather than kind = 'person'. I joined through
nomination_people since companies, like people, are credited via that
junction table. COUNT(DISTINCT nomination_id) avoids over-counting if a
win nomination credits Pixar alongside other parties."

**Result:** `0`. The query is syntactically and structurally correct by
every rule in the prompt, and returns a clean, confident-looking number
that is flatly wrong — Pixar's films have many real wins.

**Rules exercised:** `kind = 'company'` selection correctly applied;
`nomination_people` join path correct in form; `COUNT(DISTINCT
nomination_id)` correct per the counting rule. Every mechanical rule fired
correctly — the failure is that no `people` row named "Pixar" exists at
all, which no rule anticipated.

**Gap found → fixed in v0.8:** checked directly — `people` has no row
matching `%Pixar%` under any kind. The only "Pixar" text anywhere in the
database is incidental prose inside five Sci-Tech `citation` strings
(individuals credited "at Pixar" or "of Pixar's Renderman/USD/Presto"),
not a structured nominee credit. Sampled well-known Pixar films directly
against `nomination_films`/`nominations`: Finding Nemo, The Incredibles,
Ratatouille, Up (2009), Brave, Inside Out, Coco, and Soul all have real
wins (mostly Animated Feature Film, plus Sound Editing, Music (Scoring),
Music (Song)) — so the true win count is well above zero, just not
reachable through any company-credit row. Checked scope: Warner Bros. and
Disney both have `kind = 'company'` rows (several historical name
variants, from Best-Picture-era studio credits); Marvel and Netflix, like
Pixar, have none. `kind = 'company'` coverage is essentially an
early-Hollywood-studio-credit artifact, not a general studio index — the
existing rule's phrasing didn't warn that a company search returning zero
rows can mean "not tracked as a nominee" rather than "zero wins." Added a
TRAP in v0.8 (see changelog) naming this and requiring the model to say so
rather than reporting a bare zero.

**Note on scope:** even under v0.8's new rule, this specific question
still can't be given a correct numeric answer from this schema — the fix
makes the model surface the coverage gap honestly instead of asserting
`0`, but there is no structural path from "Pixar" to "which films it
produced" (no studio/production-company column on `films` at all). A
fully correct answer would require refusing outright, similar to stretch
case 1, or answering "0 *credited directly to Pixar as a company* — but
this schema doesn't track studio production credits, so this likely
undercounts." Whether the prompt should push all the way to refusal here,
or is right to stop at "say so and give the honest partial number," is an
open question — flagging rather than deciding, since it borders on the
same aggregate-scope-ambiguity shape flagged as open after cases 8 and 9.

---

### Stretch 3 — PASS

**Question:** What's the longest Best Picture winner?

**Generated SQL:**
```sql
SELECT
    f.film_id,
    f.title,
    f.release_year,
    f.runtime_minutes
FROM nominations n
JOIN categories cat ON cat.category_id = n.category_id
JOIN nomination_films nf ON nf.nomination_id = n.nomination_id
JOIN films f ON f.film_id = nf.film_id
WHERE cat.award_group = 'Best Picture'
  AND n.is_winner = 1
  AND f.runtime_minutes IS NOT NULL
ORDER BY f.runtime_minutes DESC
LIMIT 5;
```

**Generated explanation:** "'Best Picture' matches award_group directly.
I filtered runtime_minutes IS NOT NULL before ordering, since a NULL
shouldn't silently win or lose the ranking by accident — SQLite would
actually sort NULLs last in DESC order here regardless, but filtering
explicitly makes that guarantee visible rather than relying on an
implementation detail. LIMIT 5 shows the top few for context, matching
the youngest-winner pattern."

**Result:** Gone with the Wind (1939, 238 min), Lawrence of Arabia (1962,
227), Ben-Hur (1959, 212), The Godfather Part II (1974, 202), The Lord of
the Rings: The Return of the King (2003, 201).

**NULL check (specifically requested):** 0 of the 98 Best Picture winners
have NULL runtime_minutes. The IS NOT NULL guard is good defensive
practice and correctly applied, but it changed nothing here — coverage is
complete for this particular slice of films (Best Picture winners are
well-documented mainstream films with complete IMDb metadata), unlike
`runtime_minutes`' general ~NULL rate across the full 5,265-film table.
Had the guard been omitted, SQLite's own NULL-sorts-last-in-DESC behavior
would have produced the same top 5 anyway — but that's an implementation
detail not worth depending on.

**Rules exercised:** award_group exact-match (no colloquial mapping
needed — "Best Picture" is already a literal award_group string); INNER
JOIN correct for a films-are-the-point question; disambiguating columns.

**Compare:** not one of the 12 original Phase 5a queries or a notebook
cell — no ground truth artifact. Verified by hand: Gone with the Wind at
238 minutes is the correct, well-documented real-world answer.

**Gaps found:** none.

---

### Stretch 4 — PASS

**Question:** Which directors won Best Picture but were never nominated
for Directing?

**Generated SQL:**
```sql
SELECT DISTINCT
    p.person_id,
    p.name,
    p.birth_year,
    f.film_id,
    f.title,
    f.release_year
FROM film_directors fd
JOIN people p ON p.person_id = fd.person_id
JOIN films f ON f.film_id = fd.film_id
JOIN nomination_films nf ON nf.film_id = f.film_id
JOIN nominations n ON n.nomination_id = nf.nomination_id
JOIN categories cat ON cat.category_id = n.category_id
WHERE cat.award_group = 'Best Picture'
  AND n.is_winner = 1
  AND p.person_id NOT IN (
      SELECT np.person_id
      FROM nomination_people np
      JOIN nominations dn ON dn.nomination_id = np.nomination_id
      JOIN categories dcat ON dcat.category_id = dn.category_id
      WHERE dcat.award_group = 'Directing'
  )
ORDER BY f.release_year;
```

**Generated explanation:** "Started from film_directors, not nominations,
per the JOIN PATHS rule — deriving directors from a Directing-category
nomination would only find nominated directors, which is the opposite of
what this question needs. award_group = 'Directing' (not class) for the
Assistant Director trap. Included birth_year and film release_year per
the disambiguation rules."

**Result:** 5 rows — Edmund Goulding (Grand Hotel, 1932), Loveleen Tandan
(Slumdog Millionaire, 2008), Ben Affleck (Argo, 2012), Peter Farrelly
(Green Book, 2018), Sian Heder (CODA, 2021).

**Rules exercised:** film_directors as the director source (not the
Directing category); the Assistant Director class trap; disambiguation
columns; NOT IN anti-join against nomination_people scoped to Directing.

**Compare against case 9 (the film-centric framing of the same question):**
identical 5 people and films, same order by release_year. The two framings
— "Best Picture winners whose director wasn't nominated" (start from
nominations, LEFT JOIN to film_directors) vs. "directors who won Best
Picture but weren't nominated" (start from film_directors, INNER JOIN to
nominations) — agree exactly. Wings correctly absent from both: it has no
`film_directors` row at all, so this person-centric framing structurally
can't name a "director" for it in the first place (there's nothing to
INNER JOIN from), which is a different mechanism than case 9's LEFT JOIN
producing a NULL-person row that then fails the NOT IN check — but the
same film ends up excluded from the final answer either way, for the
right underlying reason (no known director to evaluate).

**Gaps found:** none. This confirms the two framings are handled
consistently — no inconsistency between the film-centric and
person-centric versions of the same underlying question.

---

### Regression check — cases 1, 5, 8 against v0.8

Re-ran all three from scratch against the current prompt rather than
assuming earlier fixes still hold, since v0.8 touched the same
IDENTIFYING FILMS AND PEOPLE section that cases 2/3/8's rules live in.

**Case 1** (list all ceremonies): `ORDER BY ceremony ASC`, all 98 rows,
ceremony 1 (1927/28) through 98 (2025). Matches the v0.7 fix and notebook
1.1's ground truth exactly — no drift.

**Case 5** (most-nominated non-winners): top 10 identical to the
originally-logged result, same names, same counts, same order (Greg P.
Russell 16 ... Ren Klyce 9). No drift.

**Case 8** (most wins, total-count reading): top 10 identical to the
originally-logged result (Walt Disney 26 ... Edith Head 8). No drift —
in particular, v0.8's new kind = 'company' TRAP had no effect here, as
expected, since this query filters kind = 'person' and never touches
company rows.

**Verdict:** no regression in any of the three. The v0.6/v0.7/v0.8 fixes
were each scoped to the specific mechanism they targeted (fan-out on
non-aggregate listings; LIMIT-truncation-conditional ordering; company
zero-result honesty) without touching the ranked-query ORDER BY logic
that cases 5 and 8 depend on, or the ascending-order fix case 1 depends
on.

---

## Remaining cases

All 11 numbered cases and all 4 stretch cases from `docs/text_to_sql.md` are
done. No queued cases remain — see the end-of-run report for regression
results and next steps.

---

## Method

The model generating SQL must see **only** the system prompt above and the
question. Not this file's eval log, not `docs/text_to_sql.md`, not the notebook.
Rule gaps only surface when the model is working from the prompt alone.

Comparison targets, where they exist: `notebooks/oscar_sql_tutorial.ipynb`
(~19 tested queries) and `queries/*.sql`. Character-identical SQL is not the
bar — same result set is. A legitimate alternative formulation is a pass.

Known expected divergence: the notebook uses exact `=` for person lookups
(query 3.2); the prompt mandates `LIKE`. Same rows, different SQL. Pass.

The eval log must record the model's explanation text alongside the SQL and
results, not just the SQL and results. The output format requires the model
to state which hierarchy level it chose and how it handled any ambiguity in
the question — we currently have no record of whether that is actually
happening, since every case so far logged the SQL and the verdict but not
the accompanying prose.
