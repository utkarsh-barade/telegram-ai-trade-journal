"""
Authentication & Authorization service.

Provides JWT token encoding/decoding, password hashing, and user authentication
against configured environment credentials.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Optional

import jwt

# Secret key for JWT signing
JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-trade-journal-key-change-in-prod")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours default

# Admin user credentials
DEFAULT_USER: str = os.getenv("DASHBOARD_USERNAME", "admin")
DEFAULT_PASS: str = os.getenv("DASHBOARD_PASSWORD", "admin123")


def hash_password(password: str, salt: str = "trade_journal_salt") -> str:
    """Generate SHA-256 HMAC hash of a password."""
    return hmac.new(salt.encode("utf-8"), password.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against the hashed password."""
    return hmac.compare_digest(hash_password(plain_password), hashed_password)


# Default stored admin hash
_STORED_ADMIN_HASH = hash_password(DEFAULT_PASS)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """
    Authenticate user credentials.
    Returns user dict if valid, else None.
    """
    if username.strip().lower() == DEFAULT_USER.lower():
        if verify_password(password, _STORED_ADMIN_HASH):
            return {
                "username": DEFAULT_USER,
                "role": "admin",
                "display_name": "Head Analyst",
            }
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.
    Returns payload dict if valid, else None.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
