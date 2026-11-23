import json
from pathlib import Path

from app.db import pool

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "corpus_sample.json"


def load(path: Path = SAMPLE) -> int:
    articles = json.loads(path.read_text())["articles"]
    with pool.connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO legal_articles (ref, code, title, text, valid_from, valid_to)
            VALUES (%(ref)s, %(code)s, %(title)s, %(text)s, %(valid_from)s, %(valid_to)s)
            ON CONFLICT (ref) DO UPDATE SET text = EXCLUDED.text, title = EXCLUDED.title,
                valid_from = EXCLUDED.valid_from, valid_to = EXCLUDED.valid_to
            """,
            [{"valid_from": None, "valid_to": None, **a} for a in articles],
        )
    return len(articles)


def search(question: str, k: int = 4) -> list[dict]:
    with pool.connection() as conn:
        return conn.execute(
            """
            SELECT ref, code, title, text,
                   ts_rank_cd(search, websearch_to_tsquery('french', %(q)s)) AS score
              FROM legal_articles
             WHERE (valid_to IS NULL OR valid_to >= current_date)
               AND search @@ websearch_to_tsquery('french', %(q)s)
             ORDER BY score DESC
             LIMIT %(k)s
            """,
            {"q": _or_query(question), "k": k},
        ).fetchall()


def _or_query(question: str) -> str:
    words = [w.strip("?!.,;:'\"()").lower() for w in question.split()]
    return " or ".join(w for w in words if len(w) > 3) or question


def get(refs: list[str]) -> dict[str, dict]:
    if not refs:
        return {}
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT ref, text, valid_to FROM legal_articles WHERE ref = ANY(%s)", (refs,)
        ).fetchall()
    return {r["ref"]: r for r in rows}
