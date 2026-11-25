"""API anahtarı doğrulama ve imzalı OAuth 'state' üretimi."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import re
import time
from typing import Optional
from urllib.parse import urlparse
from fastapi import Header, HTTPException

STATE_TTL_SECONDS = 900
DEFAULT_RETURN_HOSTS = "studio.likyastudios.live,likyastudio.github.io"


def _secret() -> str:
    return os.getenv("API_SECRET_KEY", "").strip()


SESSION_TTL_SECONDS = 14 * 24 * 3600
LOGIN_CODE_TTL_SECONDS = 120


def allowed_emails() -> set[str]:
    """Panele girebilen Google hesapları. Liste yalnız sunucu ayarında durur (depo herkese açık)."""
    return {e.strip().lower() for e in re.split(r"[\s,;/]+", os.getenv("ALLOWED_LOGIN_EMAILS", "")) if e.strip()}


def make_token(kind: str, data: dict, ttl: int) -> str:
    payload = {**data, "k": kind, "e": int(time.time()) + ttl}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{body}.{_sign(body, kind)}"


def read_token(token: str, kind: str) -> Optional[dict]:
    if not _secret() or "." not in (token or ""):
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig.encode(), _sign(body, kind).encode()):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        return None
    if data.get("k") != kind or int(data.get("e", 0)) < time.time():
        return None
    return data


def session_email(token: Optional[str]) -> Optional[str]:
    """Geçerli oturumun e-postası. Liste her istekte yeniden bakılır: listeden çıkan hesap hemen kapanır."""
    data = read_token(token or "", "session")
    email = (data or {}).get("m", "")
    return email if email and email in allowed_emails() else None


def make_login_code(email: str, challenge: str) -> str:
    return make_token("login-code", {"m": email, "c": challenge}, LOGIN_CODE_TTL_SECONDS)


def exchange_login_code(code: str, verifier: str) -> Optional[str]:
    """Kod, yalnız girişi başlatan tarayıcıdaki gizli 'verifier' ile oturuma çevrilir (PKCE mantığı)."""
    data = read_token(code, "login-code")
    if not data or not hmac.compare_digest(
        hashlib.sha256(verifier.encode()).hexdigest().encode(), str(data.get("c", "")).encode()
    ):
        return None
    return data["m"] if data["m"] in allowed_emails() else None


def verify_api_key(
    x_api_key: Optional[str] = Header(default=None),
    x_session: Optional[str] = Header(default=None),
):
    """Panel: Google oturumu (X-Session). Otomasyonlar: API anahtarı (X-API-Key)."""
    if x_session and not x_api_key:
        if session_email(x_session):
            return
        raise HTTPException(status_code=401, detail="Oturum geçersiz veya süresi dolmuş.")
    expected = _secret()
    if not expected:
        # Anahtar tanımsızsa herkese açmak yerine kapat (yerel geliştirme için açıkça izin verilebilir)
        if os.getenv("ALLOW_NO_API_KEY") == "1":
            return
        raise HTTPException(status_code=503, detail="Sunucuda API_SECRET_KEY tanımlı değil.")
    if not hmac.compare_digest((x_api_key or "").encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Geçersiz X-API-Key.")


def is_allowed_return_url(url: str) -> bool:
    hosts = {h.strip() for h in os.getenv("OAUTH_RETURN_HOSTS", DEFAULT_RETURN_HOSTS).split(",") if h.strip()}
    u = urlparse(url)
    if u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1"):
        return True
    return u.scheme == "https" and u.hostname in hosts and not u.username


def _sign(body: str, kind: str = "oauth-state") -> str:
    return hmac.new(_secret().encode(), (kind + ":" + body).encode(), hashlib.sha256).hexdigest()


def make_state(platform: str, redirect_to: str, brand: str) -> str:
    payload = {"p": platform, "r": redirect_to, "b": brand, "e": int(time.time()) + STATE_TTL_SECONDS}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"{body}.{_sign(body)}"


def read_state(state: str, *platforms: str) -> dict:
    bad = HTTPException(status_code=400, detail="Bağlantı isteği geçersiz veya süresi dolmuş. Panelden yeniden deneyin.")
    if not _secret() or "." not in (state or ""):
        raise bad
    body, sig = state.rsplit(".", 1)
    if not hmac.compare_digest(sig.encode(), _sign(body).encode()):
        raise bad
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        raise bad
    if data.get("p") not in platforms or int(data.get("e", 0)) < time.time():
        raise bad
    return data


def verify_scheduler(
    x_api_key: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
    x_session: Optional[str] = Header(default=None),
):
    """API anahtarı ya da Cloud Scheduler'ın Google imzalı kimliği (OIDC). Sunucuda/görevde anahtar saklamaya gerek kalmaz."""
    email = os.getenv("SCHEDULER_SA_EMAIL", "").strip()
    audience = os.getenv("PUBLIC_API_BASE", "").rstrip("/")
    if email and audience and (authorization or "").startswith("Bearer ") and not x_api_key:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token
        try:
            info = id_token.verify_oauth2_token(authorization[7:], GoogleRequest(), audience=audience)
        except Exception:
            raise HTTPException(status_code=401, detail="Zamanlayıcı kimliği doğrulanamadı.")
        if info.get("email") == email and info.get("email_verified"):
            return
        raise HTTPException(status_code=401, detail="Zamanlayıcı kimliği yetkili değil.")
    verify_api_key(x_api_key, x_session)
