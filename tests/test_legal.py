from app.main import answer


def test_answers_with_verified_citation(client):
    r = client.post("/ask", json={"question": "Quelle est la durée légale du travail par semaine ?"}).json()
    assert r["status"] == "answered"
    assert any("L3121-27" in c["citations"] for c in r["verified"])


def test_hallucinated_article_is_rejected(client):
    def lying_llm(question, passages):
        return [{"text": "Selon l'article L9999-42, la durée légale est de 32 heures.",
                 "citations": ["L9999-42"], "kind": "verified"}]

    r = answer("Quelle est la durée légale du travail par semaine ?", generate=lying_llm)
    assert r["status"] == "refused"
    assert "inexistante" in r["rejected_claims"][0]["reason"]


def test_mixed_answer_keeps_only_grounded_claims(client):
    def mixed_llm(question, passages):
        return [
            {"text": "La durée légale de travail effective est fixée à trente-cinq heures par semaine.",
             "citations": ["L3121-27"], "kind": "verified"},
            {"text": "Les heures au-delà ouvrent donc droit à une majoration.",
             "citations": ["L3121-27"], "kind": "verified"},
            {"text": "L'article L3121-99 prévoit une prime.", "citations": ["L3121-27"], "kind": "verified"},
        ]

    r = answer("durée légale du travail semaine", generate=mixed_llm)
    assert r["status"] == "answered"
    assert len(r["verified"]) == 1
    assert len(r["interpretations"]) == 1          # rétrogradée faute de support littéral
    assert "L3121-99" in r["rejected_claims"][0]["reason"]


def test_refuses_out_of_scope_question(client):
    r = client.post("/ask", json={"question": "Comment déclarer une cryptomonnaie aux impôts ?"}).json()
    assert r["status"] == "refused"
