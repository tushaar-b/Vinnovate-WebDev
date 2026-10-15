from typing import Optional
from fastapi import APIRouter, HTTPException, status, Request, Header
from pydantic import BaseModel, Field
from app.services.auth import (
    verify_admin_password,
    create_session_token,
    verify_session_token,
    get_configured_admin_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    password: str = Field(..., description="Administrative password")


class LoginResponse(BaseModel):
    token: str
    expires_at: int
    user: str = "admin"


class AuthStatusResponse(BaseModel):
    authenticated: bool
    user: Optional[str] = None


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """
    Authenticates operator with administrative password and issues a signed session token.
    """
    if not verify_admin_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid administrative password."}},
        )

    token, expires_at = create_session_token(subject="admin")
    return LoginResponse(token=token, expires_at=expires_at, user="admin")


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    Returns current authentication state for the client without throwing 401.
    Useful for frontend initialization and session checks.
    """
    # 1. Check Bearer token
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_val = parts[1].strip()
            payload = verify_session_token(token_val)
            if payload:
                return AuthStatusResponse(authenticated=True, user=payload.get("sub", "admin"))
            configured_pass = get_configured_admin_password()
            if configured_pass and token_val == configured_pass:
                return AuthStatusResponse(authenticated=True, user="admin")

    # 2. Check X-API-Key header
    if x_api_key:
        payload = verify_session_token(x_api_key.strip())
        if payload:
            return AuthStatusResponse(authenticated=True, user=payload.get("sub", "admin"))
        configured_pass = get_configured_admin_password()
        if configured_pass and x_api_key.strip() == configured_pass:
            return AuthStatusResponse(authenticated=True, user="admin")

    # 3. Check Cookie
    cookie_token = request.cookies.get("session_token") or request.cookies.get("access_token")
    if cookie_token:
        payload = verify_session_token(cookie_token)
        if payload:
            return AuthStatusResponse(authenticated=True, user=payload.get("sub", "admin"))

    return AuthStatusResponse(authenticated=False, user=None)


@router.post("/logout")
def logout():
    """Logs out by clearing client session."""
    return {"status": "logged_out"}
