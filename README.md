# L'IA qui invente — RAG vérifié

[![ci-cd](https://github.com/Vanloukdom/legal-rag-verifier/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Vanloukdom/legal-rag-verifier/actions/workflows/ci-cd.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791) ![k3s](https://img.shields.io/badge/k3s-deploy-FFC61C)

> Projet **09/10** de la série *« 10 problèmes que tout ingénieur logiciel devrait savoir résoudre »*.
> Démo : `https://legal.apps.vansoreldatacloud.com` · Documentation interactive : `https://legal.apps.vansoreldatacloud.com/docs`

> ⚠️ `data/corpus_sample.json` est un **corpus de démonstration** : les textes sont des résumés. En production, importez le texte officiel et consolidé depuis Légifrance, avec les dates de vigueur.

## Le problème

Une IA intégrée à une application juridique répond avec assurance en citant un **article de loi inexistant**. La réponse a l'air parfaitement crédible. Comment vérifier les références, **séparer le vérifié de l'interprétation** et **refuser** quand les preuves manquent ?

## La solution

Pipeline en 4 étapes, où **le modèle n'a jamais le dernier mot** :

1. **Recherche** dans un corpus officiel versionné (recherche plein texte PostgreSQL en français, uniquement les articles **en vigueur**). Sous un seuil de pertinence → **refus**.
2. **Génération contrainte** : le LLM (Claude, si `ANTHROPIC_API_KEY` est fourni) ne reçoit que les extraits et doit renvoyer du JSON `{text, citations, kind}`. Sans clé, **mode extractif** (aucune hallucination possible).
3. **Vérification déterministe** de chaque affirmation :
   - toute référence (citée **ou mentionnée dans le texte**, par regex) doit **exister** dans le corpus ;
   - elle doit faire partie des extraits **effectivement récupérés** ;
   - le texte doit être **soutenu** par l'extrait (recouvrement lexical). Sinon, l'affirmation « vérifiée » est **rétrogradée en interprétation**.
4. **Réponse structurée** : `verified`, `interpretations`, `rejected_claims` (avec la raison), `sources` et avertissement. **Aucune affirmation vérifiée → refus.**

Chaque réponse est **journalisée** (`answer_audit`) pour mesurer le taux d'hallucination.

## Architecture

```mermaid
flowchart LR
    Q[Question] --> R[Recherche corpus en vigueur]
    R -- rien de pertinent --> X[Refus]
    R --> G[LLM contraint aux extraits]
    G --> V{Vérificateur}
    V -- article inexistant --> REJ[Rejeté]
    V -- non soutenu --> INT[Interprétation]
    V -- soutenu --> VER[Vérifié]
    VER --> A[Réponse + sources]
    INT --> A
```

## API

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/ask` | Question → réponse vérifiée ou refus |
| GET | `/articles/{ref}` | Texte d'un article du corpus |

### Démo

```bash
URL=https://legal.apps.vansoreldatacloud.com
curl -s -XPOST $URL/ask -H 'content-type: application/json' \
  -d '{"question":"Quelle est la durée maximale de la période d essai pour un cadre ?"}' | jq
```

## Lancer en local

```bash
docker compose up --build          # API sur http://localhost:8000/docs
```

## Tests

```bash
docker compose up -d db
pip install -r requirements.txt -r requirements-dev.txt
ADMIN_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres pytest -q
```

Ce qui est prouvé : Réponse avec citation vérifiée ; **article inventé (L9999-42) → refus** ; réponse mixte → seule l'affirmation fondée reste « vérifiée », la déduction devient une interprétation, la fausse référence est rejetée ; question hors corpus → refus.

## Déploiement en production (k3s sur VPS)

Pipeline GitHub Actions `test → build → deploy` :

1. **test** : pytest avec PostgreSQL en service ;
2. **build** : image multi-couches poussée sur `ghcr.io/vanloukdom/legal-rag-verifier` (tags `sha` et `latest`) ;
3. **deploy** : `kubectl apply -k k8s/` dans le namespace `p09-legal`, puis attente du `rollout status`.

Secrets à créer dans *Settings → Secrets and variables → Actions* :

| Secret | Contenu |
|---|---|
| `KUBECONFIG_B64` | `base64 -w0 kubeconfig` du cluster k3s (sans ce secret, l'étape deploy est ignorée) |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL (fixe : ne pas le changer après le premier déploiement) |
| `APP_SECRET` | `openssl rand -hex 32` |

Côté cluster : Traefik (inclus dans k3s), cert-manager avec un `ClusterIssuer` `letsencrypt-prod`, un enregistrement DNS `*.apps.vansoreldatacloud.com` vers le VPS, et le package GHCR passé en **public** (ou un `imagePullSecret`).

Sécurité des pods : utilisateur non root, système de fichiers en lecture seule, capabilities supprimées, requests/limits, probes `/healthz` et `/readyz`, métriques Prometheus sur `/metrics`.

## Pour aller plus loin

Importer le Code du travail complet via l'API Légifrance (PISTE) ; recherche hybride BM25 + embeddings (pgvector) ; vérification NLI par un second modèle ; jeu d'évaluation annoté.

---
Van Sorel LOUKDOM · DevOps / Cloud & Data Engineer · Licence MIT
