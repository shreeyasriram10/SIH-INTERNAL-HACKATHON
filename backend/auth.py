"""Authentication primitives: password hashing, JWT issue/verify, and the
FastAPI dependencies used to protect endpoints."""

import logging
import os
import secrets
import time
from datetime import datetime, timezone, timedelta

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
import models

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("LOHA_TOKEN_TTL_MIN", 60 * 12))

# The signing key MUST come from the environment in any deployed setting. We fall
# back to a per-process random key so that a misconfigured deploy fails closed
# (tokens simply stop validating across restarts) instead of shipping a key that
# is public in the source tree.
SECRET_KEY = os.environ.get("LOHA_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(48)
    logger.warning(
        "LOHA_SECRET_KEY is not set - generated an ephemeral signing key. "
        "Sessions will not survive a restart. Set LOHA_SECRET_KEY in production."
    )

# Credentials for the seeded demo accounts. These are ordinary users created by
# seed_data with real bcrypt hashes; there is no login path that bypasses the
# password check.
DEMO_ACCOUNTS = {
    "admin@sail.gov.in": ("Chief Logistics Officer", "Admin"),
    "analyst@sail.gov.in": ("SAIL Procurement Analyst", "Analyst"),
    "officer@sail.gov.in": ("SAIL Procurement Officer", "Procurement Officer"),
}
DEMO_PASSWORD = os.environ.get("LOHA_DEMO_PASSWORD", "12345")

# The browser session travels in an httpOnly cookie so that script injected into
# the page cannot read it; localStorage offered no such protection. Bearer
# tokens still work for programmatic clients (Swagger, curl, integration tests).
SESSION_COOKIE = "loha_session"

# Secure cookies are refused by clients over plain http, which would silently
# break local development and the test suite. Derive the flag from the actual
# request scheme - behind a proxy that terminates TLS the original scheme
# arrives in x-forwarded-proto - and allow an explicit override.
_COOKIE_SECURE_OVERRIDE = os.environ.get("LOHA_COOKIE_SECURE")


def cookie_is_secure(request) -> bool:
    if _COOKIE_SECURE_OVERRIDE is not None:
        return _COOKIE_SECURE_OVERRIDE != "0"
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return (forwarded or request.url.scheme) == "https"

# Registration is closed by default. Set LOHA_SIGNUP_DOMAINS to a comma-separated
# allow-list ("sail.in,gov.in") to permit self-service sign-up for those domains
# only; anything else has to be created by an administrator. Open registration
# handed an Analyst role - and every endpoint it unlocks - to any passer-by.
SIGNUP_DOMAINS = [
    d.strip().lower().lstrip("@")
    for d in os.environ.get("LOHA_SIGNUP_DOMAINS", "").split(",")
    if d.strip()
]

# Login throttling. In-process, so on serverless it is per-container rather than
# global - it blunts credential stuffing but is not a substitute for a shared
# rate limiter at the edge.
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOHA_LOGIN_MAX_ATTEMPTS", 8))
LOGIN_WINDOW_SEC = int(os.environ.get("LOHA_LOGIN_WINDOW_SEC", 300))
_login_attempts: dict[str, list] = {}


def signup_allowed(email: str) -> bool:
    """Whether this address may create its own account."""
    if not SIGNUP_DOMAINS:
        return False
    domain = email.rsplit("@", 1)[-1].lower()
    return any(domain == d or domain.endswith("." + d) for d in SIGNUP_DOMAINS)


def register_login_failure(key: str) -> None:
    now = time.time()
    attempts = [t for t in _login_attempts.get(key, []) if now - t < LOGIN_WINDOW_SEC]
    attempts.append(now)
    _login_attempts[key] = attempts


def clear_login_failures(key: str) -> None:
    _login_attempts.pop(key, None)


def login_is_throttled(key: str) -> bool:
    now = time.time()
    attempts = [t for t in _login_attempts.get(key, []) if now - t < LOGIN_WINDOW_SEC]
    _login_attempts[key] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def _to_bcrypt_bytes(password: str) -> bytes:
    """bcrypt silently ignores input past 72 *bytes*, so truncate on bytes
    rather than characters — slicing the str would let a multibyte password
    overflow the limit and hash inconsistently."""
    return password.encode("utf-8")[:72]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed/legacy hash in the row — treat as a failed login, never as a pass.
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated. Sign in to continue.",
    headers={"WWW-Authenticate": "Bearer"},
)


def _extract_token(request: Request, bearer: str | None) -> str | None:
    """Session cookie first, Authorization header second.

    The browser never handles the token itself; the header path exists for
    Swagger and other programmatic clients.
    """
    cookie = request.cookies.get(SESSION_COOKIE)
    return cookie or bearer


def _resolve_user(token: str | None, db: Session):
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    return db.query(models.User).filter(models.User.email == payload["sub"]).first()


def get_current_user(
    request: Request,
    bearer: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    user = _resolve_user(_extract_token(request, bearer), db)
    if user is None:
        raise CREDENTIALS_EXCEPTION
    return user


def get_optional_user(
    request: Request,
    bearer: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User | None:
    """For endpoints that attribute an action to a signed-in user but do not
    require one."""
    return _resolve_user(_extract_token(request, bearer), db)


def require_roles(*roles: str):
    """Dependency factory: restrict an endpoint to the given roles."""

    def _guard(user: models.User = Depends(get_current_user)) -> models.User:
        if roles and user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(roles)}. Your role: {user.role}.",
            )
        return user

    return _guard
