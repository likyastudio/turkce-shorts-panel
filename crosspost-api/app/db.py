"""Database layer: PostgreSQL via DATABASE_URL (Cloud SQL / Supabase / Neon),
with automatic SQLite fallback for zero-config local dev & testing."""
from __future__ import annotations
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

DATABASE_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH = os.getenv("SQLITE_PATH", "/tmp/likya_crosspost.db")


def _is_pg() -> bool:
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


@contextmanager
def get_conn():
    if _is_pg():
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        try:
            yield conn, "%s", True
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        os.makedirs(os.path.dirname(SQLITE_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn, "?", False
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _rows(cur, is_pg: bool) -> list[dict[str, Any]]:
    if is_pg:
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def init_db() -> None:
    # Cloud Run'da sessizce geçici SQLite'a düşmek planları kaybettirir; açıkça dur.
    if os.getenv("K_SERVICE") and not _is_pg():
        raise RuntimeError("DATABASE_URL (PostgreSQL) tanımlı değil; Cloud Run'da SQLite kullanılamaz.")
    with get_conn() as (conn, _p, is_pg):
        cur = conn.cursor()
        if is_pg:
            schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
            cur.execute(open(schema_path, encoding="utf-8").read())
        else:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS social_accounts (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform      TEXT NOT NULL CHECK (platform IN ('YT', 'IG')),
                    brand         TEXT NOT NULL DEFAULT 'akilalmaz',
                    account_name  TEXT NOT NULL,
                    external_id   TEXT NOT NULL,
                    access_token  TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at    TEXT,
                    created_at    TEXT NOT NULL,
                    UNIQUE (platform, external_id)
                );
                CREATE TABLE IF NOT EXISTS publish_logs (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id          TEXT NOT NULL,
                    account_id        INTEGER,
                    platform          TEXT NOT NULL CHECK (platform IN ('YT', 'IG')),
                    account_name      TEXT,
                    status            TEXT NOT NULL DEFAULT 'Bekliyor',
                    platform_post_url TEXT,
                    error_message     TEXT,
                    created_at        TEXT NOT NULL,
                    updated_at        TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_publish_logs_video ON publish_logs (video_id, updated_at);
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    brand           TEXT NOT NULL DEFAULT 'akilalmaz',
                    video_id        TEXT NOT NULL,
                    video_url       TEXT NOT NULL,
                    title           TEXT NOT NULL,
                    description     TEXT NOT NULL,
                    ig_caption      TEXT,
                    cover_url       TEXT,
                    thumb_offset_ms INTEGER DEFAULT 1500,
                    account_ids     TEXT NOT NULL DEFAULT '[]',
                    scheduled_at    TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'Planlandı',
                    yt_uploaded     INTEGER NOT NULL DEFAULT 0,
                    yt_video_url    TEXT,
                    yt_sync_started_at TEXT,
                    error_message   TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scheduled_posts_due ON scheduled_posts (status, scheduled_at);
                """
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_account(
    platform: str,
    account_name: str,
    external_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[str] = None,
    brand: str = "akilalmaz",
) -> dict[str, Any]:
    now = _now()
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, refresh_token FROM social_accounts WHERE platform={p} AND external_id={p}",
            (platform, external_id),
        )
        existing = _rows(cur, is_pg)
        if existing:
            acc_id = existing[0]["id"]
            keep_refresh = refresh_token or existing[0].get("refresh_token")
            cur.execute(
                f"UPDATE social_accounts SET account_name={p}, access_token={p}, refresh_token={p}, expires_at={p} WHERE id={p}",
                (account_name, access_token, keep_refresh, expires_at, acc_id),
            )
        else:
            if is_pg:
                cur.execute(
                    "INSERT INTO social_accounts (platform, brand, account_name, external_id, access_token, refresh_token, expires_at, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (platform, brand, account_name, external_id, access_token, refresh_token, expires_at, now),
                )
                acc_id = cur.fetchone()[0]
            else:
                cur.execute(
                    "INSERT INTO social_accounts (platform, brand, account_name, external_id, access_token, refresh_token, expires_at, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (platform, brand, account_name, external_id, access_token, refresh_token, expires_at, now),
                )
                acc_id = cur.lastrowid
        cur.execute(
            f"SELECT id, platform, brand, account_name, external_id, expires_at, created_at FROM social_accounts WHERE id={p}",
            (acc_id,),
        )
        return _rows(cur, is_pg)[0]


def list_accounts(include_tokens: bool = False, brand: Optional[str] = None) -> list[dict[str, Any]]:
    cols = (
        "id, platform, brand, account_name, external_id, access_token, refresh_token, expires_at, created_at"
        if include_tokens
        else "id, platform, brand, account_name, external_id, expires_at, created_at"
    )
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        if brand:
            cur.execute(f"SELECT {cols} FROM social_accounts WHERE brand={p} ORDER BY platform, id", (brand,))
        else:
            cur.execute(f"SELECT {cols} FROM social_accounts ORDER BY brand, platform, id")
        return _rows(cur, is_pg)


def set_account_brand(account_id: int, brand: str) -> bool:
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(f"UPDATE social_accounts SET brand={p} WHERE id={p}", (brand, account_id))
        return cur.rowcount > 0


def get_accounts_by_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        ph = ",".join([p] * len(ids))
        cur.execute(
            f"SELECT id, platform, brand, account_name, external_id, access_token, refresh_token, expires_at FROM social_accounts WHERE id IN ({ph})",
            tuple(ids),
        )
        return _rows(cur, is_pg)


def update_account_token(account_id: int, access_token: str, expires_at: Optional[str]) -> None:
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"UPDATE social_accounts SET access_token={p}, expires_at={p} WHERE id={p}",
            (access_token, expires_at, account_id),
        )


def delete_account(account_id: int) -> bool:
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(f"DELETE FROM social_accounts WHERE id={p}", (account_id,))
        return cur.rowcount > 0


def create_publish_log(
    video_id: str,
    platform: str,
    account_id: Optional[int] = None,
    account_name: Optional[str] = None,
    status: str = "Bekliyor",
) -> int:
    now = _now()
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        if is_pg:
            cur.execute(
                "INSERT INTO publish_logs (video_id, account_id, platform, account_name, status, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (video_id, account_id, platform, account_name, status, now, now),
            )
            return cur.fetchone()[0]
        cur.execute(
            "INSERT INTO publish_logs (video_id, account_id, platform, account_name, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (video_id, account_id, platform, account_name, status, now, now),
        )
        return int(cur.lastrowid)


def update_publish_log(
    log_id: int,
    status: str,
    platform_post_url: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    now = _now()
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"UPDATE publish_logs SET status={p}, platform_post_url=COALESCE({p}, platform_post_url), "
            f"error_message={p}, updated_at={p} WHERE id={p}",
            (status, platform_post_url, error_message, now, log_id),
        )


def list_publish_logs(video_id: Optional[str] = None) -> list[dict[str, Any]]:
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        if video_id:
            cur.execute(
                f"SELECT id, video_id, account_id, platform, account_name, status, platform_post_url, error_message, created_at, updated_at "
                f"FROM publish_logs WHERE video_id={p} ORDER BY id DESC LIMIT 50",
                (video_id,),
            )
        else:
            cur.execute(
                "SELECT id, video_id, account_id, platform, account_name, status, platform_post_url, error_message, created_at, updated_at "
                "FROM publish_logs ORDER BY id DESC LIMIT 200"
            )
        return _rows(cur, is_pg)


_SCHED_COLS = (
    "id, brand, video_id, video_url, title, description, ig_caption, cover_url, thumb_offset_ms, "
    "account_ids, scheduled_at, status, yt_uploaded, yt_video_url, error_message, created_at, updated_at"
)


def _norm_sched_row(r: dict[str, Any]) -> dict[str, Any]:
    import json as _json
    for k in ("scheduled_at", "created_at", "updated_at"):
        if isinstance(r.get(k), datetime):
            r[k] = r[k].astimezone(timezone.utc).isoformat()
    if isinstance(r.get("account_ids"), str):
        try:
            r["account_ids"] = _json.loads(r["account_ids"])
        except Exception:
            r["account_ids"] = []
    r["yt_uploaded"] = bool(r.get("yt_uploaded"))
    r["brand"] = r.get("brand") or "akilalmaz"
    return r


def create_scheduled_post(
    video_id: str,
    video_url: str,
    title: str,
    description: str,
    scheduled_at_iso: str,
    ig_caption: Optional[str] = None,
    cover_url: Optional[str] = None,
    thumb_offset_ms: int = 1500,
    account_ids: Optional[list[int]] = None,
    brand: str = "akilalmaz",
) -> dict[str, Any]:
    import json as _json
    now = _now()
    acc_json = _json.dumps(account_ids or [])
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        if is_pg:
            cur.execute(
                "INSERT INTO scheduled_posts "
                "(brand, video_id, video_url, title, description, ig_caption, cover_url, thumb_offset_ms, account_ids, scheduled_at, status, yt_uploaded, created_at, updated_at) "
                f"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Planlandı',FALSE,%s,%s) RETURNING {_SCHED_COLS}",
                (brand, video_id, video_url, title, description, ig_caption, cover_url, thumb_offset_ms, acc_json, scheduled_at_iso, now, now),
            )
            return _norm_sched_row(_rows(cur, True)[0])
        cur.execute(
            "INSERT INTO scheduled_posts "
            "(brand, video_id, video_url, title, description, ig_caption, cover_url, thumb_offset_ms, account_ids, scheduled_at, status, yt_uploaded, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,'Planlandı',0,?,?)",
            (brand, video_id, video_url, title, description, ig_caption, cover_url, thumb_offset_ms, acc_json, scheduled_at_iso, now, now),
        )
        rid = int(cur.lastrowid)
        cur.execute(f"SELECT {_SCHED_COLS} FROM scheduled_posts WHERE id=?", (rid,))
        return _norm_sched_row(_rows(cur, False)[0])


def list_scheduled_posts(status: Optional[str] = None, brand: Optional[str] = None) -> list[dict[str, Any]]:
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        conds, vals = [], []
        if status:
            conds.append(f"status={p}")
            vals.append(status)
        if brand:
            conds.append(f"brand={p}")
            vals.append(brand)
        where = f"WHERE {' AND '.join(conds)}" if conds else ""
        cur.execute(f"SELECT {_SCHED_COLS} FROM scheduled_posts {where} ORDER BY scheduled_at DESC LIMIT 500", tuple(vals))
        return [_norm_sched_row(r) for r in reversed(_rows(cur, is_pg))]


def get_scheduled_post(post_id: int) -> Optional[dict[str, Any]]:
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        cur.execute(f"SELECT {_SCHED_COLS} FROM scheduled_posts WHERE id={p}", (post_id,))
        rows = _rows(cur, is_pg)
        return _norm_sched_row(rows[0]) if rows else None


SYNC_STALE_MINUTES = 20  # yarım kalan YouTube yüklemesi bu süreden sonra yeniden denenebilir


def _ago(minutes: int) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def claim_scheduled_post(post_id: int, statuses: tuple[str, ...] = ("Planlandı",)) -> bool:
    """Gönderiyi tek bir çalıştırıcıya ayırır (atomik). Aynı anda gelen ikinci istek False alır."""
    now = _now()
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        ph = ",".join([p] * len(statuses))
        cur.execute(
            f"UPDATE scheduled_posts SET status='Yayınlanıyor', error_message=NULL, updated_at={p} "
            f"WHERE id={p} AND status IN ({ph}) AND (yt_sync_started_at IS NULL OR yt_sync_started_at < {p})",
            (now, post_id, *statuses, _ago(SYNC_STALE_MINUTES)),
        )
        return cur.rowcount == 1


def claim_yt_sync(post_id: int) -> bool:
    """YouTube ön-yüklemesini tek çalıştırıcıya ayırır (atomik)."""
    now = _now()
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        flag = "FALSE" if is_pg else "0"
        cur.execute(
            f"UPDATE scheduled_posts SET yt_sync_started_at={p} "
            f"WHERE id={p} AND status='Planlandı' AND yt_uploaded={flag} AND scheduled_at > {p} "
            f"AND (yt_sync_started_at IS NULL OR yt_sync_started_at < {p})",
            (now, post_id, now, _ago(SYNC_STALE_MINUTES)),
        )
        return cur.rowcount == 1


def release_yt_sync(post_id: int, error_message: Optional[str] = None) -> None:
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"UPDATE scheduled_posts SET yt_sync_started_at=NULL, error_message=COALESCE({p}, error_message) WHERE id={p}",
            (error_message, post_id),
        )


def fail_stale_publishing(minutes: int = 30) -> int:
    """Sunucu kapanınca 'Yayınlanıyor'da kalan gönderileri Hata'ya alır. Çift yayın olmasın diye
    otomatik tekrar denenmez; kullanıcı kanalı kontrol edip karar verir."""
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"UPDATE scheduled_posts SET status='Hata', error_message={p}, updated_at={p} "
            f"WHERE status='Yayınlanıyor' AND updated_at < {p}",
            ("Yayın yarım kaldı. Kanalda yayınlanıp yayınlanmadığını kontrol edip tekrar deneyin.", _now(), _ago(minutes)),
        )
        return cur.rowcount


def get_published_account_ids(post: dict[str, Any]) -> set[int]:
    """Bu plan oluşturulduktan sonra videonun başarıyla gönderildiği hesaplar."""
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"SELECT account_id FROM publish_logs WHERE video_id={p} AND status IN ('Yayında','YT Planlandı') "
            f"AND account_id IS NOT NULL AND created_at >= {p}",
            (post["video_id"], post["created_at"]),
        )
        return {int(r[0]) for r in cur.fetchall()}


def get_publish_logs_by_ids(ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        ph = ",".join([p] * len(ids))
        cur.execute(f"SELECT id, status, error_message, platform_post_url FROM publish_logs WHERE id IN ({ph})", tuple(ids))
        return _rows(cur, is_pg)


def edit_scheduled_post(post_id: int, fields: dict[str, Any]) -> bool:
    """Yalnızca henüz yayınlanmamış (Planlandı/Hata) gönderinin metnini/saatini değiştirir."""
    allowed = {k: v for k, v in fields.items() if k in ("title", "description", "ig_caption", "scheduled_at", "status")}
    if not allowed:
        return False
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        sets = ", ".join(f"{k}={p}" for k in allowed)
        cur.execute(
            f"UPDATE scheduled_posts SET {sets}, error_message=NULL, updated_at={p} "
            f"WHERE id={p} AND status IN ('Planlandı','Hata') AND (yt_sync_started_at IS NULL OR yt_sync_started_at < {p})",
            (*allowed.values(), _now(), post_id, _ago(SYNC_STALE_MINUTES)),
        )
        return cur.rowcount == 1


def get_due_scheduled_posts(now_iso: Optional[str] = None) -> list[dict[str, Any]]:
    cutoff = now_iso or _now()
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        cur.execute(
            f"SELECT {_SCHED_COLS} FROM scheduled_posts WHERE status='Planlandı' AND scheduled_at <= {p} ORDER BY scheduled_at ASC LIMIT 20",
            (cutoff,),
        )
        return [_norm_sched_row(r) for r in _rows(cur, is_pg)]


def get_pending_yt_presync_posts(limit: int = 5) -> list[dict[str, Any]]:
    """Returns upcoming scheduled posts not yet pre-uploaded to YouTube Studio."""
    now = _now()
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        flag = "FALSE" if is_pg else "0"
        cur.execute(
            f"SELECT {_SCHED_COLS} FROM scheduled_posts "
            f"WHERE status='Planlandı' AND yt_uploaded={flag} AND scheduled_at > {p} "
            f"ORDER BY scheduled_at ASC LIMIT {int(limit)}",
            (now,),
        )
        return [_norm_sched_row(r) for r in _rows(cur, is_pg)]


def count_yt_uploads_today() -> int:
    """Counts YouTube uploads/pre-uploads in the last 24 hours to stay safely within YT Data API free quota."""
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM publish_logs WHERE platform='YT' AND status IN ('Yayında','YT Planlandı') AND created_at >= {p}",
            (since,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0


def mark_scheduled_yt_uploaded(post_id: int, yt_video_url: str, error_message: Optional[str] = None) -> None:
    now = _now()
    with get_conn() as (conn, p, is_pg):
        cur = conn.cursor()
        flag = True if is_pg else 1
        cur.execute(
            f"UPDATE scheduled_posts SET yt_uploaded={p}, yt_video_url={p}, yt_sync_started_at=NULL, error_message={p}, updated_at={p} WHERE id={p}",
            (flag, yt_video_url, error_message, now, post_id),
        )


def update_scheduled_post(post_id: int, status: str, error_message: Optional[str] = None) -> None:
    now = _now()
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"UPDATE scheduled_posts SET status={p}, error_message={p}, updated_at={p} WHERE id={p}",
            (status, error_message, now, post_id),
        )


def reschedule_post(post_id: int, scheduled_at_iso: str, account_ids: Optional[list[int]] = None) -> Optional[dict[str, Any]]:
    import json
    now = _now()
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        if account_ids is not None:
            cur.execute(
                f"UPDATE scheduled_posts SET scheduled_at={p}, status='Planlandı', error_message=NULL, account_ids={p}, updated_at={p} WHERE id={p}",
                (scheduled_at_iso, json.dumps(account_ids), now, post_id),
            )
        else:
            cur.execute(
                f"UPDATE scheduled_posts SET scheduled_at={p}, status='Planlandı', error_message=NULL, updated_at={p} WHERE id={p}",
                (scheduled_at_iso, now, post_id),
            )
    return get_scheduled_post(post_id)


def delete_scheduled_post(post_id: int) -> bool:
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(f"DELETE FROM scheduled_posts WHERE id={p}", (post_id,))
        return cur.rowcount > 0


def update_scheduled_cover_url(video_id: str, cover_url: str) -> int:
    now = _now()
    with get_conn() as (conn, p, _is_pg):
        cur = conn.cursor()
        cur.execute(
            f"UPDATE scheduled_posts SET cover_url={p}, updated_at={p} WHERE video_id={p}",
            (cover_url, now, video_id),
        )
        return cur.rowcount

