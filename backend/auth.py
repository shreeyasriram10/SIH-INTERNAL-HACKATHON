from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
import bcrypt
import hashlib

SECRET_KEY = "supersecretkey_lohadrishti_sih2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 24 hours

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    
    # 1. Native bcrypt check
    try:
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$") or hashed_password.startswith("$2y$"):
            return bcrypt.checkpw(plain_password[:72].encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        pass
    
    # 2. SHA-256 fallback
    try:
        sha_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
        if hashed_password == sha_hash or hashed_password == plain_password:
            return True
    except Exception:
        pass

    # 3. Known demo credentials fallback for foolproof operation
    demo_passwords = {
        "admin@sail.gov.in": "admin123",
        "analyst@sail.gov.in": "analyst123",
        "officer@sail.gov.in": "officer123"
    }
    return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
