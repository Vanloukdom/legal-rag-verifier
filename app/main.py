import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app import corpus, generator, verifier
from app.db import close_db, init_db, pool
from app.observability import setup_observability

MIN_RETRIEVAL_SCORE = float(os.getenv("MIN_RETRIEVAL_SCORE", "0.05"))
DISCLAIMER = "Information juridique générale, pas un conseil. Consultez un avocat pour votre situation."


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    corpus.load()
    yield
    close_db()


app = FastAPI(
    title="Legal RAG verifier",
    description="RAG juridique qui vérifie chaque référence et refuse de répondre sans preuve.",
    version="1.0.0",
    lifespan=lifespan,
)
setup_observability(app)


class Question(BaseModel):
    question: str = Field(min_length=5, max_length=1000)


def answer(question: str, generate=None) -> dict:
    generate = generate or generator.generate
    passages = [p for p in corpus.search(question) if p["score"] >= MIN_RETRIEVAL_SCORE]
    if not passages:
        return _refuse(question, "Aucun texte pertinent trouvé dans le corpus vérifié.")

    claims = generate(question, passages)
    accepted, rejected = verifier.verify(claims, {p["ref"] for p in passages})
    if not any(c["kind"] == "verified" for c in accepted):
        return _refuse(question, "Les preuves sont insuffisantes pour répondre avec certitude.", rejected)

    _audit(question, "answered", rejected)
    return {
        "status": "answered",
        "verified": [c for c in accepted if c["kind"] == "verified"],
        "interpretations": [c for c in accepted if c["kind"] == "interpretation"],
        "rejected_claims": rejected,
        "sources": [{"ref": p["ref"], "code": p["code"], "title": p["title"]} for p in passages],
        "disclaimer": DISCLAIMER,
    }


def _refuse(question, reason, rejected=None):
    _audit(question, "refused", rejected or [])
    return {"status": "refused", "reason": reason, "rejected_claims": rejected or [], "disclaimer": DISCLAIMER}


def _audit(question, outcome, rejected):
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO answer_audit (question, outcome, rejected) VALUES (%s, %s, %s)",
            (question, outcome, Jsonb(rejected)),
        )


@app.post("/ask")
def ask(body: Question):
    return answer(body.question)


@app.get("/articles/{ref}")
def article(ref: str):
    return corpus.get([ref]).get(ref) or {"detail": "Article absent du corpus vérifié"}
