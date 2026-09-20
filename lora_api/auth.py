import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from typing import Optional
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from lora_api.config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRY_HOURS,
)

security = HTTPBearer(auto_error=False)
_SALT = None


def _get_salt() -> bytes:
    global _SALT
    if _SALT is None:
        _SALT = JWT_SECRET.encode()[:16].ljust(16, b'\x00')
    return _SALT


def hash_password(password: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), _get_salt(), 100000)
    return dk.hex()


def verify_password(plain: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(plain), hashed)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    # 1. Check Bearer credentials
    if credentials and credentials.credentials:
        return decode_token(credentials.credentials)

    raise HTTPException(status_code=401, detail="Not authenticated")
