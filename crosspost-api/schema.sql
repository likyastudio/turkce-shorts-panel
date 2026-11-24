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

CREATE TABLE IF NOT EXISTS scheduled_posts (
    id              SERIAL PRIMARY KEY,
    video_id        TEXT NOT NULL,
    video_url       TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    ig_caption      TEXT,
    cover_url       TEXT,
    thumb_offset_ms INTEGER DEFAULT 1500,
    account_ids     TEXT NOT NULL DEFAULT '[]',
    scheduled_at    TIMESTAMPTZ NOT NULL,
    status          VARCHAR(24) NOT NULL DEFAULT 'Planlandı',
    yt_uploaded     BOOLEAN NOT NULL DEFAULT FALSE,
    yt_video_url    TEXT,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE social_accounts ADD COLUMN IF NOT EXISTS brand VARCHAR(32) NOT NULL DEFAULT 'akilalmaz';
ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS yt_uploaded BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS yt_video_url TEXT;
ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS yt_sync_started_at TIMESTAMPTZ;
ALTER TABLE scheduled_posts ADD COLUMN IF NOT EXISTS brand VARCHAR(32) NOT NULL DEFAULT 'akilalmaz';

CREATE INDEX IF NOT EXISTS idx_scheduled_posts_due ON scheduled_posts (status, scheduled_at ASC);

