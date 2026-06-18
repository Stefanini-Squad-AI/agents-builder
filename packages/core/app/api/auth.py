"""Stub auth API for development.

This is a placeholder that always returns success. Replace with real
authentication (JWT + password hashing) before production.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _create_stub_jwt() -> str:
    """Create a minimal valid JWT for development (unsigned, not for production)."""
    header = {"alg": "none", "typ": "JWT"}
    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "admin@example.com",
        "name": "Admin User",
        "role": "owner",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
    }
    
    def b64url(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()
    
    return f"{b64url(header)}.{b64url(payload)}."


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class AuthUser(BaseModel):
    id: str
    email: str
    name: str
    role: str
    tenant_id: str
    tenant_name: str
    created_at: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24 hours
    user: AuthUser


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 86400


# Stub user for development
_STUB_USER = AuthUser(
    id=str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
    email="admin@example.com",
    name="Admin User",
    role="owner",
    tenant_id=str(uuid.UUID("00000000-0000-0000-0000-000000000001")),
    tenant_name="Default Tenant",
    created_at=datetime.now(timezone.utc).isoformat(),
)


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> LoginResponse:
    """Stub login — always succeeds in development."""
    return LoginResponse(
        access_token=_create_stub_jwt(),
        refresh_token=_create_stub_jwt(),
        user=_STUB_USER,
    )


@router.post("/logout")
def logout() -> dict[str, str]:
    """Stub logout."""
    return {"status": "ok"}


@router.post("/refresh", response_model=RefreshTokenResponse)
def refresh(request: RefreshTokenRequest) -> RefreshTokenResponse:
    """Stub token refresh."""
    return RefreshTokenResponse(
        access_token=_create_stub_jwt(),
        refresh_token=_create_stub_jwt(),
    )


@router.get("/me", response_model=AuthUser)
def get_current_user() -> AuthUser:
    """Return stub user."""
    return _STUB_USER
