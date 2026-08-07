# Text-to-SQL demo: sends a natural-language question + schema.sql + the
# prompts/system_prompt.txt rules to a Claude model via CBORG (LBNL's
# LiteLLM gateway), extracts the generated SQL, validates it, and runs
# it read-only against oscars.db.
# Run: uv run src/text_to_sql.py [--quiet] [--model NAME] <question>
#   uv run src/text_to_sql.py "Which films won the most Oscars?"
#   uv run src/text_to_sql.py --quiet "Who won Best Picture in 2023?"
#   uv run src/text_to_sql.py --model lbl/cborg-chat "Which films won the most Oscars?"

import os
import re
import sqlite3
import sys
from pathlib import Path

import anthropic
import pandas as pd

CBORG_BASE_URL = "https://api.cborg.lbl.gov"
DEFAULT_MODEL = "claude-sonnet-5"

DB_PATH = "oscars.db"
SCHEMA_PATH = Path("schema.sql")
PROMPT_PATH = Path("prompts/system_prompt.txt")

SQL_FENCE_RE = re.compile(r"```sql\s*(.*?)```", re.DOTALL)


def usage():
    print("usage: uv run src/text_to_sql.py [--quiet] [--model NAME] <question>")


def load_system_prompt():
    if not SCHEMA_PATH.exists():
        print(f"error: {SCHEMA_PATH} not found", file=sys.stderr)
        sys.exit(1)
    if not PROMPT_PATH.exists():
        print(f"error: {PROMPT_PATH} not found", file=sys.stderr)
        sys.exit(1)
    return PROMPT_PATH.read_text().replace("{schema_sql}", SCHEMA_PATH.read_text())


def strip_leading_comments(sql):
    """Strip -- line comments and /* */ block comments from the start of sql."""
    s = sql.lstrip()
    while True:
        if s.startswith("--"):
            nl = s.find("\n")
            s = s[nl + 1:].lstrip() if nl != -1 else ""
        elif s.startswith("/*"):
            end = s.find("*/")
            s = s[end + 2:].lstrip() if end != -1 else ""
        else:
            return s


def validate_sql(sql):
    """Accept SELECT/WITH only, after stripping leading comments; reject
    multiple statements. Returns (ok, error_message)."""
    body = strip_leading_comments(sql).strip()
    upper = body.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return False, "generated query must start with SELECT or WITH"
    if body.endswith(";"):
        body = body[:-1]
    if ";" in body:
        return False, "multiple statements are not allowed"
    return True, None


def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    args = [a for a in args if a != "--quiet"]

    model = DEFAULT_MODEL
    if "--model" in args:
        idx = args.index("--model")
        if idx + 1 >= len(args):
            usage()
            sys.exit(1)
        model = args[idx + 1]
        del args[idx:idx + 2]

    if not args:
        usage()
        sys.exit(1)
    question = " ".join(args)

    api_key = os.environ.get("CBORG_API_KEY")
    if not api_key:
        print("error: CBORG_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    system_prompt = load_system_prompt()

    client = anthropic.Anthropic(api_key=api_key, base_url=CBORG_BASE_URL)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
    except anthropic.APIError as e:
        print(f"error: API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    text = "".join(block.text for block in response.content if block.type == "text")
    sql_blocks = SQL_FENCE_RE.findall(text)
    explanation = SQL_FENCE_RE.sub("", text).strip()

    if not sql_blocks:
        # Designed refusal path: the prompt tells the model to emit no SQL
        # when a question is unanswerable from this schema.
        print(explanation)
        sys.exit(0)

    if len(sql_blocks) > 1:
        print(
            f"warning: model returned {len(sql_blocks)} sql blocks; using the first",
            file=sys.stderr,
        )

    sql = sql_blocks[0].strip()
    ok, error = validate_sql(sql)
    if not ok:
        print(f"error: rejected generated SQL: {error}")
        print(sql)
        sys.exit(1)

    if not quiet:
        print(sql)
        print()

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        cur = conn.execute(sql)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    except sqlite3.Error as e:
        print(f"error: SQL execution failed: {e}")
        print(sql)
        sys.exit(1)
    finally:
        conn.close()

    if not rows:
        # Zero rows from a clean, valid query can still be a wrong answer
        # (e.g. searching for a company this schema doesn't credit as a
        # nominee) — the explanation is the only diagnostic available.
        print("0 rows.")
        if explanation:
            print(explanation)
        return

    df = pd.DataFrame(rows, columns=columns)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
