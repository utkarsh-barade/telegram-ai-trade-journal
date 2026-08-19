"""
Authentication endpoints and FastAPI dependency for route protection.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Auth"])
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str
    display_name: str


class UserProfile(BaseModel):
    username: str
    role: str
    display_name: str


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    FastAPI dependency to protect endpoints.
    Requires a valid Bearer JWT token in Authorization header.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = auth_service.decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "username": payload["sub"],
        "role": payload.get("role", "analyst"),
        "display_name": payload.get("display_name", payload["sub"]),
    }


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Authenticate username and password to get a JWT access token."""
    user = auth_service.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = auth_service.create_access_token(
        data={
            "sub": user["username"],
            "role": user["role"],
            "display_name": user["display_name"],
        }
    )

    return LoginResponse(
        access_token=token,
        username=user["username"],
        role=user["role"],
        display_name=user["display_name"],
    )


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Return profile details for current authenticated user."""
    return UserProfile(
        username=current_user["username"],
        role=current_user["role"],
        display_name=current_user["display_name"],
    )
