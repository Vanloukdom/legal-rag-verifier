"""Vérification post-génération : chaque référence doit exister, être en vigueur,
avoir été récupérée, et soutenir réellement l'affirmation."""
import re
import unicodedata

from app import corpus

REF_PATTERN = re.compile(r"\b([LRD])\s?\.?\s?(\d{3,4}(?:-\d+){1,3})\b")
STOP = set("le la les de des du un une et en est à au aux par pour que qui ne pas sur dans son sa ses ce cette il elle peut".split())
SUPPORT_THRESHOLD = 0.5


def extract_refs(text: str) -> set[str]:
    return {f"{m.group(1)}{m.group(2)}" for m in REF_PATTERN.finditer(text)}


def _tokens(text: str) -> set[str]:
    norm = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z0-9]+", norm) if w not in STOP and len(w) > 2}


def support(claim: str, source: str) -> float:
    c = _tokens(claim)
    return len(c & _tokens(source)) / len(c) if c else 0.0


def verify(claims: list[dict], retrieved_refs: set[str]) -> tuple[list[dict], list[dict]]:
    accepted, rejected = [], []
    all_refs = set().union(*(set(c.get("citations", [])) | extract_refs(c.get("text", "")) for c in claims)) if claims else set()
    known = corpus.get(sorted(all_refs))
    for claim in claims:
        cited = set(claim.get("citations", [])) | extract_refs(claim.get("text", ""))
        if not cited:
            rejected.append({**claim, "reason": "aucune source citée"})
            continue
        invented = [r for r in cited if r not in known]
        if invented:
            rejected.append({**claim, "reason": f"référence inexistante : {', '.join(sorted(invented))}"})
            continue
        if not cited <= retrieved_refs:
            rejected.append({**claim, "reason": "source non issue de la recherche"})
            continue
        score = max(support(claim["text"], known[r]["text"]) for r in cited)
        kind = claim.get("kind", "interpretation")
        if kind == "verified" and score < SUPPORT_THRESHOLD:
            kind = "interpretation"  # rétrogradé : l'extrait ne le dit pas littéralement
        accepted.append({"text": claim["text"], "citations": sorted(cited), "kind": kind, "support": round(score, 2)})
    return accepted, rejected
