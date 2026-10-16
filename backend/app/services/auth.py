import hmac
import hashlib
import json
import base64
import time
import secrets
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import Request, Header, HTTPException, status, Depends
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


class AuthContext:
    def __init__(
        self,
        subject: str,
        role: str = "admin",
        judge_session_id: Optional[str] = None,
    ):
        self.subject = subject
        self.role = role  # "admin" or "judge"
        self.judge_session_id = judge_session_id

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_judge(self) -> bool:
        return self.role == "judge"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.subject == other or (self.is_admin and other == "admin")
        if isinstance(other, AuthContext):
            return (
                self.subject == other.subject
                and self.role == other.role
                and self.judge_session_id == other.judge_session_id
            )
        return False

    def __str__(self) -> str:
        return self.subject

    def __repr__(self) -> str:
        return f"<AuthContext sub={self.subject} role={self.role} jid={self.judge_session_id}>"


def create_session_token(
    subject: str = "admin",
    expires_in_seconds: int = 7 * 86400,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> Tuple[str, int]:
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
    if extra_claims:
        payload.update(extra_claims)

    payload_json = json.dumps(payload, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8").rstrip("=")

    secret = get_signing_secret()
    signature = hmac.new(secret, payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{payload_b64}.{sig_b64}", exp


def create_judge_session_token(judge_session_id: str, expires_in_seconds: int = 86400) -> Tuple[str, int]:
    """
    Generates a scoped, expiring judge session token.
    """
    return create_session_token(
        subject=f"judge:{judge_session_id}",
        expires_in_seconds=expires_in_seconds,
        extra_claims={
            "role": "judge",
            "judge_session_id": judge_session_id,
        },
    )


def resolve_auth_payload(payload: Dict[str, Any]) -> AuthContext:
    sub = payload.get("sub", "admin")
    role = payload.get("role")
    judge_session_id = payload.get("judge_session_id")
    if role == "judge" or (isinstance(sub, str) and sub.startswith("judge:")):
        jid = judge_session_id or (sub.split("judge:", 1)[1] if "judge:" in sub else None)
        return AuthContext(subject=sub, role="judge", judge_session_id=jid)
    return AuthContext(subject=sub, role="admin", judge_session_id=None)


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
) -> AuthContext:
    """
    FastAPI dependency protecting routes from unauthenticated access.
    Returns AuthContext representing admin or judge session.
    """
    # Test mode bypass for legacy phase tests (when TEST_AUTH_ENABLED is False and no credentials sent)
    if settings.TEST_MODE and not getattr(settings, "TEST_AUTH_ENABLED", False):
        if not authorization and not x_api_key:
            ctx = AuthContext("test-user", role="admin")
            request.state.auth = ctx
            return ctx

    # 1. Check Authorization: Bearer <token>
    if authorization:
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token_val = parts[1].strip()

            # A. Check signed session token
            payload = verify_session_token(token_val)
            if payload:
                ctx = resolve_auth_payload(payload)
                request.state.auth = ctx
                return ctx

            # B. Check if token matches static API_KEY or ADMIN_PASSWORD directly
            configured_api_key = getattr(settings, "API_KEY", None)
            if configured_api_key and secrets.compare_digest(token_val, configured_api_key.strip()):
                ctx = AuthContext("api-key-user", role="admin")
                request.state.auth = ctx
                return ctx

            configured_pass = get_configured_admin_password()
            if configured_pass and secrets.compare_digest(token_val, configured_pass):
                ctx = AuthContext("admin", role="admin")
                request.state.auth = ctx
                return ctx

    # 2. Check X-API-Key header
    if x_api_key:
        key_val = x_api_key.strip()
        configured_api_key = getattr(settings, "API_KEY", None)
        if configured_api_key and secrets.compare_digest(key_val, configured_api_key.strip()):
            ctx = AuthContext("api-key-user", role="admin")
            request.state.auth = ctx
            return ctx

        configured_pass = get_configured_admin_password()
        if configured_pass and secrets.compare_digest(key_val, configured_pass):
            ctx = AuthContext("admin", role="admin")
            request.state.auth = ctx
            return ctx

        # Check if X-API-Key was passed as a session token
        payload = verify_session_token(key_val)
        if payload:
            ctx = resolve_auth_payload(payload)
            request.state.auth = ctx
            return ctx

    # 3. Check Cookie
    cookie_token = request.cookies.get("session_token") or request.cookies.get("access_token")
    if cookie_token:
        payload = verify_session_token(cookie_token)
        if payload:
            ctx = resolve_auth_payload(payload)
            request.state.auth = ctx
            return ctx

    # 4. Check Query Parameter (specifically useful for <img> tag media requests)
    query_token = request.query_params.get("token") or request.query_params.get("auth_token")
    if query_token:
        payload = verify_session_token(query_token)
        if payload:
            ctx = resolve_auth_payload(payload)
            request.state.auth = ctx
            return ctx
        configured_pass = get_configured_admin_password()
        if configured_pass and secrets.compare_digest(query_token, configured_pass):
            ctx = AuthContext("admin", role="admin")
            request.state.auth = ctx
            return ctx

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "UNAUTHORIZED", "message": "Authentication required to access this resource."}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_auth_context(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> AuthContext:
    """Dependency that retrieves or resolves AuthContext for the current request."""
    if hasattr(request.state, "auth") and isinstance(request.state.auth, AuthContext):
        return request.state.auth
    return require_auth(request, authorization, x_api_key)


def require_admin_auth(
    auth: AuthContext = Depends(require_auth),
) -> AuthContext:
    """Dependency strictly requiring administrative privileges."""
    if not auth.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "Administrative access required."}},
        )
    return auth


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
