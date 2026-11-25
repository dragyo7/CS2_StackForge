from __future__ import annotations

import hashlib
import hmac
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserSession

SESSION_TTL_DAYS = 14
_LOGIN_ATTEMPTS: dict[str, list[datetime]] = defaultdict(list)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return f"pbkdf2_sha256$260000${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iters_s, salt, expected_hex = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iters_s))
        return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _check_rate_limit(email_key: str) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=5)
    recent = [t for t in _LOGIN_ATTEMPTS[email_key] if t > cutoff]
    _LOGIN_ATTEMPTS[email_key] = recent
    if len(recent) >= 10:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in 5 minutes.")
    recent.append(now)


def signup_user(db: Session, email: str, username: str, password: str) -> tuple[User, str]:
    clean_email = email.strip().lower()
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    if db.scalar(select(User).where(User.email == clean_email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=clean_email,
        username=username.strip(),
        password_hash=hash_password(password),
        role="HOST",
    )
    db.add(user)
    db.flush()
    token = _create_session(db, user.id)
    db.commit()
    db.refresh(user)
    return user, token


def login_user(db: Session, email: str, password: str) -> tuple[User, str]:
    clean_email = email.strip().lower()
    _check_rate_limit(clean_email)
    user = db.scalar(select(User).where(User.email == clean_email, User.is_active.is_(True)))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _LOGIN_ATTEMPTS.pop(clean_email, None)
    token = _create_session(db, user.id)
    db.commit()
    return user, token


def _create_session(db: Session, user_id: str) -> str:
    raw = secrets.token_urlsafe(32)
    sess = UserSession(
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS),
    )
    db.add(sess)
    return raw


def logout_token(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    th = _hash_token(raw_token)
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == th))
    if sess:
        db.delete(sess)
        db.commit()


def get_optional_user(db: Session, authorization: str | None = Header(default=None)) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    raw = authorization.split(" ", 1)[1].strip()
    if not raw:
        return None
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == _hash_token(raw)))
    if not sess:
        return None
    exp = sess.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        return None
    return db.scalar(select(User).where(User.id == sess.user_id, User.is_active.is_(True)))
