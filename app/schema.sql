CREATE TABLE IF NOT EXISTS legal_articles (
    ref         TEXT PRIMARY KEY,           -- ex. L3121-27
    code        TEXT NOT NULL,
    title       TEXT NOT NULL,
    text        TEXT NOT NULL,
    valid_from  DATE,
    valid_to    DATE,                       -- NULL = en vigueur
    search      TSVECTOR GENERATED ALWAYS AS (
                    setweight(to_tsvector('french', coalesce(title, '')), 'A') ||
                    setweight(to_tsvector('french', text), 'B')) STORED
);
CREATE INDEX IF NOT EXISTS legal_articles_search ON legal_articles USING GIN (search);

CREATE TABLE IF NOT EXISTS answer_audit (
    id          BIGSERIAL PRIMARY KEY,
    question    TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    rejected    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
