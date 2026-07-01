import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from lora_api.config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRY_HOURS, TELEGRAM_USER_ID

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
    return hash_password(plain) == hashed


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
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None:
        return {"sub": str(TELEGRAM_USER_ID)}
    return decode_token(credentials.credentials)
