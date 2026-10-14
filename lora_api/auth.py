import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from typing import Optional
from fastapi import HTTPException, Depends, Request, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from lora_api.config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRY_HOURS,
    STANDD_API_TOKEN,
)


async def require_standd_token(
    authorization: str | None = Header(default=None),
) -> bool:
    """Permite tokenul read-only Standd sau JWT-ul existent al dashboardului."""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing service token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token")
    if STANDD_API_TOKEN and hmac.compare_digest(token.encode("utf-8"), STANDD_API_TOKEN.encode("utf-8")):
        return True
    # Compatibilitate: dashboardul continuă să folosească JWT pe aceleași GET-uri.
    try:
        decode_token(token)
    except HTTPException as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token") from exc
    return True

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
    if credentials and credentials.credentials and STANDD_API_TOKEN:
        service_paths = {"/api/tasks", "/api/calendar/week", "/api/finances/summary", "/api/health"}
        if request.method == "GET" and request.url.path in service_paths:
            if hmac.compare_digest(credentials.credentials.encode("utf-8"), STANDD_API_TOKEN.encode("utf-8")):
                return {"sub": "standd", "service": True}
    # 1. Check Bearer credentials
    if credentials and credentials.credentials:
        return decode_token(credentials.credentials)

    raise HTTPException(status_code=401, detail="Not authenticated")
