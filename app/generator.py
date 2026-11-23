"""Génération : LLM contraint (si ANTHROPIC_API_KEY) ou mode extractif sans LLM."""
import json
import os

import httpx

API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SYSTEM = """Tu es un assistant juridique. Règles absolues :
- Réponds UNIQUEMENT à partir des extraits fournis entre balises <article>.
- Chaque affirmation cite au moins une référence présente dans les extraits.
- N'invente jamais de numéro d'article.
- Marque "verified" ce qui est dit littéralement par un extrait, "interpretation" ce que tu en déduis.
- Si les extraits ne suffisent pas, renvoie une liste vide.
Réponds en JSON : {"claims": [{"text": "...", "citations": ["L1234-5"], "kind": "verified|interpretation"}]}"""


def generate(question: str, passages: list[dict]) -> list[dict]:
    if not API_KEY:
        return extractive(question, passages)
    context = "\n".join(f'<article ref="{p["ref"]}">{p["text"]}</article>' for p in passages)
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01"},
        json={
            "model": MODEL,
            "max_tokens": 1024,
            "system": SYSTEM,
            "messages": [{"role": "user", "content": f"{context}\n\nQuestion : {question}"}],
        },
        timeout=30,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1]).get("claims", []) if start >= 0 else []


def extractive(_: str, passages: list[dict]) -> list[dict]:
    """Sans LLM : on restitue les extraits pertinents, tous vérifiables par construction."""
    return [{"text": p["text"], "citations": [p["ref"]], "kind": "verified"} for p in passages[:2]]
