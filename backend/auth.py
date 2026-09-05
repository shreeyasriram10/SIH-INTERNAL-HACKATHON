"""Authentication primitives: password hashing, JWT issue/verify, and the
FastAPI dependencies used to protect endpoints."""

import logging
import os
import secrets
from datetime import datetime, timezone, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
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
    detail="Not authenticated. Provide a valid bearer token.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if not token:
        raise CREDENTIALS_EXCEPTION
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise CREDENTIALS_EXCEPTION
    user = db.query(models.User).filter(models.User.email == payload["sub"]).first()
    if user is None:
        raise CREDENTIALS_EXCEPTION
    return user


def get_optional_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User | None:
    """For endpoints that attribute an action to a user when a token is present
    but stay readable without one."""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    return db.query(models.User).filter(models.User.email == payload["sub"]).first()


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
