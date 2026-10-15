import hmac
import hashlib
import json
import base64
import time
import secrets
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, Header, HTTPException, status
from app.config import settings

logger = logging.getLogger("auth")

DEV_DEFAULT_PASSWORD = "admin"


def get_signing_secret() -> bytes:
    """
    Returns HMAC secret for signing session tokens.
    Uses AUTH_TOKEN_SECRET if configured, otherwise derives deterministically
    from ENCRYPTION_KEY, ADMIN_PASSWORD, or a stable dev seed.
    """
    explicit = getattr(settings, "AUTH_TOKEN_SECRET", None)
    if explicit and explicit.strip():
        return explicit.strip().encode("utf-8")

    seed = (
        getattr(settings, "ENCRYPTION_KEY", None)
        or getattr(settings, "ADMIN_PASSWORD", None)
        or "website_change_detector_auth_stable_seed_fallback"
    )
    return hashlib.sha256(f"auth_token_signing_secret:{seed}".encode("utf-8")).digest()


def create_session_token(subject: str = "admin", expires_in_seconds: int = 7 * 86400) -> Tuple[str, int]:
    """
    Generates a cryptographically signed HMAC-SHA256 session token.
    Returns (token_string, expires_at_timestamp).
    """
    now = int(time.time())
    exp = now + expires_in_seconds
    payload = {
        "sub": subject,
        "iat": now,
        "exp": exp,
        "nonce": secrets.token_hex(8),
    }

    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8").rstrip("=")

    secret = get_signing_secret()
    signature = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{payload_b64}.{sig_b64}", exp


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies token signature and expiration.
    Returns payload dictionary if valid, None otherwise.
    """
    if not token or "." not in token:
        return None

    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        payload_b64, sig_b64 = parts

        # Verify signature
        secret = get_signing_secret()
        expected_sig = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

        if not secrets.compare_digest(sig_b64, expected_sig_b64):
            return None

        # Pad base64 if needed
        padding = 4 - (len(payload_b64) % 4)
        if padding != 4:
            payload_b64 += "=" * padding

        payload_json = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        payload = json.loads(payload_json)

        # Check expiration
        exp = payload.get("exp", 0)
        if time.time() > exp:
            return None

        return payload
    except Exception as e:
        logger.debug(f"Token verification error: {e}")
        return None


def get_configured_admin_password() -> Optional[str]:
    """Returns the effective administrative password."""
    configured = getattr(settings, "ADMIN_PASSWORD", None)
    if configured and configured.strip():
        return configured.strip()

    is_prod = settings.ENVIRONMENT.lower() == "production"
    if is_prod:
        return None

    return DEV_DEFAULT_PASSWORD


def verify_admin_password(password: str) -> bool:
    """Validates provided password against configured admin password using constant-time check."""
    if not password or not isinstance(password, str):
        return False

    configured = get_configured_admin_password()
    if not configured:
        return False

    return secrets.compare_digest(password.strip(), configured)


def require_auth(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> str:
    """
    FastAPI dependency protecting routes from unauthenticated access.
    Supports:
    1. Bearer session token via Authorization header
    2. API Key or Bearer password via Authorization header
    3. X-API-Key header
    4. Session token via cookie
    """
    # Test mode bypass for legacy phase tests (when TEST_AUTH_ENABLED is False and no credentials sent)
    if settings.TEST_MODE and not getattr(settings, "TEST_AUTH_ENABLED", False):
        if not authorization and not x_api_key:
            return "test-user"

    # 1. Check Authorization: Bearer <token>
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_val = parts[1].strip()

            # A. Check signed session token
            payload = verify_session_token(token_val)
            if payload:
                return payload.get("sub", "admin")

            # B. Check if token matches static API_KEY or ADMIN_PASSWORD directly
            configured_api_key = getattr(settings, "API_KEY", None)
            if configured_api_key and secrets.compare_digest(token_val, configured_api_key.strip()):
                return "api-key-user"

            configured_pass = get_configured_admin_password()
            if configured_pass and secrets.compare_digest(token_val, configured_pass):
                return "admin"

    # 2. Check X-API-Key header
    if x_api_key:
        key_val = x_api_key.strip()
        configured_api_key = getattr(settings, "API_KEY", None)
        if configured_api_key and secrets.compare_digest(key_val, configured_api_key.strip()):
            return "api-key-user"

        configured_pass = get_configured_admin_password()
        if configured_pass and secrets.compare_digest(key_val, configured_pass):
            return "admin"

        # Check if X-API-Key was passed as a session token
        payload = verify_session_token(key_val)
        if payload:
            return payload.get("sub", "admin")

    # 3. Check Cookie
    cookie_token = request.cookies.get("session_token") or request.cookies.get("access_token")
    if cookie_token:
        payload = verify_session_token(cookie_token)
        if payload:
            return payload.get("sub", "admin")

    # 4. Check Query Parameter (specifically useful for <img> tag media requests)
    query_token = request.query_params.get("token") or request.query_params.get("auth_token")
    if query_token:
        payload = verify_session_token(query_token)
        if payload:
            return payload.get("sub", "admin")
        configured_pass = get_configured_admin_password()
        if configured_pass and secrets.compare_digest(query_token, configured_pass):
            return "admin"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "UNAUTHORIZED", "message": "Authentication required to access this resource."}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def validate_production_auth_at_startup() -> None:
    """
    Verifies production security configuration:
    - Enforces ADMIN_PASSWORD is set in production.
    - Enforces TEST_MODE is disabled in production.
    """
    is_prod = settings.ENVIRONMENT.lower() == "production"
    if is_prod:
        # Enforce TEST_MODE is disabled
        if settings.TEST_MODE:
            logger.warning("Disabling TEST_MODE in production environment.")
            settings.TEST_MODE = False

        # Enforce ADMIN_PASSWORD
        admin_pass = getattr(settings, "ADMIN_PASSWORD", None)
        if not admin_pass or not admin_pass.strip():
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: ADMIN_PASSWORD is required in production environment. "
                "Set ADMIN_PASSWORD in Railway environment variables to secure the system."
            )
