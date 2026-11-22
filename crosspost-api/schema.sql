-- Likya Studios Cross-Posting PostgreSQL Schema

CREATE TABLE IF NOT EXISTS social_accounts (
    id              SERIAL PRIMARY KEY,
    platform        VARCHAR(8) NOT NULL CHECK (platform IN ('YT', 'IG')),
    account_name    TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    access_token    TEXT NOT NULL,
    refresh_token   TEXT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_id)
);

CREATE TABLE IF NOT EXISTS publish_logs (
    id                SERIAL PRIMARY KEY,
    video_id          TEXT NOT NULL,
    account_id        INTEGER REFERENCES social_accounts(id) ON DELETE SET NULL,
    platform          VARCHAR(8) NOT NULL CHECK (platform IN ('YT', 'IG')),
    account_name      TEXT,
    status            VARCHAR(20) NOT NULL DEFAULT 'Bekliyor',
    platform_post_url TEXT,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_publish_logs_video ON publish_logs (video_id, updated_at DESC);
