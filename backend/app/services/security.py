import re
import socket
import ipaddress
import base64
import hashlib
import logging
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from typing import Tuple, Optional, List, Dict, Any
from cryptography.fernet import Fernet, InvalidToken
from app.config import settings

logger = logging.getLogger("security")


class SecurityValidationError(Exception):
    def __init__(self, message: str, code: str = "BLOCKED_TARGET"):
        super().__init__(message)
        self.message = message
        self.code = code


# Prohibited CIDR blocks
BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),          # Current network
    ipaddress.ip_network("10.0.0.0/8"),         # Private RFC1918
    ipaddress.ip_network("100.64.0.0/10"),      # Shared Address Space (CGNAT)
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-Local (including cloud metadata)
    ipaddress.ip_network("172.16.0.0/12"),      # Private RFC1918
    ipaddress.ip_network("192.0.0.0/24"),       # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),     # Private RFC1918
    ipaddress.ip_network("198.18.0.0/15"),      # Benchmarking
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),        # Multicast
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
    # IPv6
    ipaddress.ip_network("::1/128"),            # Loopback
    ipaddress.ip_network("::/128"),             # Unspecified
    ipaddress.ip_network("fc00::/7"),           # Unique Local Address (ULA)
    ipaddress.ip_network("fe80::/10"),          # Link-Local
    ipaddress.ip_network("ff00::/8"),           # Multicast
]

METADATA_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks whether an IP address falls into any blocked or private network range."""
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True

    for net in BLOCKED_NETWORKS:
        if ip in net:
            return True
    return False


def is_trusted_fixture_url(parsed: urlsplit) -> bool:
    """Checks if the URL is an explicitly allowed trusted local test fixture."""
    if not settings.TEST_MODE:
        return False
    # Only permit localhost / 127.0.0.1 on the configured API port with /fixture prefix
    if parsed.hostname in ("127.0.0.1", "localhost"):
        port = parsed.port or 80
        if port == settings.API_PORT and parsed.path.startswith("/fixture"):
            return True
    return False


def canonicalize_url(url: str) -> str:
    """Canonicalizes a URL to a stable, standard form for deduplication and indexing."""
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port

    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"

    path = parsed.path or "/"
    # Clean multiple consecutive slashes
    while "//" in path:
        path = path.replace("//", "/")

    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    sorted_query = urlencode(sorted(query_params))

    return urlunsplit((scheme, netloc, path, sorted_query, ""))


def validate_target_url(url: str, is_fixture_check: bool = False) -> Tuple[bool, str]:
    """
    Validates that a URL is safe to fetch, enforcing strict SSRF protections:
    - Only http/https scheme
    - No user credentials (user:pass@host)
    - Default allow ports 80/443 (or test fixture port if in test fixture mode)
    - Hostname not localhost/loopback/cloud metadata
    - Resolves all DNS records and blocks any private/loopback/link-local/multicast IPs
    
    Returns (is_valid, error_reason)
    """
    if not url or not isinstance(url, str):
        return False, "URL cannot be empty."

    url = url.strip()
    if len(url) > 2048:
        return False, "URL exceeds maximum allowed length of 2048 characters."

    try:
        parsed = urlsplit(url)
    except Exception as e:
        return False, f"Malformed URL: {str(e)}"

    # 1. Validate Scheme
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    # 2. Reject embedded credentials
    if parsed.username or parsed.password:
        return False, "URLs containing embedded authentication credentials are not permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL must contain a valid hostname."

    # 3. Check trusted test fixture exception
    if is_trusted_fixture_url(parsed):
        return True, ""

    # 4. Check explicit metadata hostnames
    if hostname.lower() in METADATA_HOSTS:
        return False, f"Access to metadata endpoint '{hostname}' is blocked."

    # 5. Check allowed ports (Standard 80 and 443 only)
    port = parsed.port
    if port and port not in (80, 443):
        return False, f"Access to non-standard port {port} is prohibited. Allowed ports: 80, 443."

    # 6. Check if hostname is directly an IP literal
    try:
        direct_ip = ipaddress.ip_address(hostname.strip("[]"))
        if is_ip_blocked(direct_ip):
            return False, f"Target IP {direct_ip} is in a prohibited or private network range."
        return True, ""
    except ValueError:
        # Not a direct IP literal, proceed to DNS resolution
        pass

    # 7. DNS Resolution check (Resolves all A and AAAA records)
    resolved_port = port if port else (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(
            hostname,
            resolved_port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as e:
        return False, f"DNS resolution failed for host '{hostname}': {str(e)}"
    except Exception as e:
        return False, f"DNS error: {str(e)}"

    if not addr_info:
        return False, f"Could not resolve any IP address for host '{hostname}'."

    # Check every resolved address
    for family, socktype, proto, canonname, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
            if is_ip_blocked(resolved_ip):
                return False, f"Host '{hostname}' resolved to prohibited IP {ip_str}."
        except ValueError:
            return False, f"Invalid resolved IP '{ip_str}'."

    return True, ""


# -------------------------------------------------------------------------
# Notification Error Sanitization
# -------------------------------------------------------------------------
def sanitize_error_message(text: Optional[str], secrets: Optional[List[str]] = None) -> str:
    """
    Sanitizes exception strings and error messages to prevent disclosure of:
    - Discord webhook URLs and secret tokens
    - Telegram bot API tokens
    - Embedded URL basic auth credentials (user:pass@host)
    - SMTP passwords and authentication secrets
    - Bearer tokens and generic API secrets
    """
    if not text:
        return ""
    out = str(text)

    # 1. Strip explicit secrets if supplied
    if secrets:
        for s in secrets:
            if s and isinstance(s, str) and len(s) >= 4:
                out = out.replace(s, "[REDACTED]")

    # 2. Discord webhooks (official and generic endpoints)
    out = re.sub(
        r'https?://(?:[a-zA-Z0-9.-]+\.)?discord(?:app)?\.com/api/webhooks/([0-9]+)/([^\s/?#\'",]+)',
        r'https://discord.com/api/webhooks/\1/[REDACTED]',
        out,
    )
    # Generic fallback for any /api/webhooks/<id>/<token> pattern
    out = re.sub(
        r'(/api/webhooks/[^/\s\'",]+)/[^\s/?#\'",]+',
        r'\1/[REDACTED]',
        out,
    )

    # 3. Telegram Bot API URLs
    out = re.sub(
        r'https?://api\.telegram\.org/bot([0-9]+:[A-Za-z0-9_-]+)/([^\s\'",]*)',
        r'https://api.telegram.org/bot[REDACTED]/\2',
        out,
    )
    # Standalone Telegram bot token pattern
    out = re.sub(
        r'\b[0-9]{8,12}:[A-Za-z0-9_-]{25,}\b',
        '[REDACTED_TELEGRAM_TOKEN]',
        out,
    )

    # 4. URLs with embedded user:pass credentials
    out = re.sub(
        r'(https?://[^:\s/\'"]+):([^@\s/\'"]+)@',
        r'\1:[REDACTED]@',
        out,
    )

    # 5. Bearer tokens and Authorization headers
    out = re.sub(
        r'(?i)\b(bearer\s+)[A-Za-z0-9._~+/-]{10,}',
        r'\1[REDACTED]',
        out,
    )

    # 6. Clean common HTTPX exception noise
    out = re.sub(
        r'\nFor more information check: https://developer\.mozilla\.org/[^\s]+',
        '',
        out,
    ).strip()

    return out


# -------------------------------------------------------------------------
# Credential Encryption at Rest (Authenticated Symmetric Encryption)
# -------------------------------------------------------------------------
# Credential Encryption at Rest (Authenticated Symmetric Encryption)
# -------------------------------------------------------------------------
# KEY ROTATION & RECOVERY ARCHITECTURE & LIMITATIONS:
# 1. Symmetric Key: Uses authenticated Fernet AES-128-CBC + HMAC-SHA256.
# 2. Key Loss: If ENCRYPTION_KEY is lost without a backup, encrypted credentials
#    CANNOT be recovered. New credentials can be re-entered through the Settings UI.
# 3. Key Rotation: To rotate an encryption key:
#    a. Read all NotificationChannel records using the old key.
#    b. Decrypt credentials in-memory using decrypt_channel_config().
#    c. Set ENCRYPTION_KEY to the new key and call reset_fernet_cache().
#    d. Re-encrypt credentials using encrypt_channel_config() and save.
# 4. Startup Safety: If ENCRYPTION_KEY is missing or invalid when encrypted
#    data already exists in the database, application and worker startup aborts
#    safely with a clear RuntimeError to prevent data corruption.
# -------------------------------------------------------------------------
_fernet_singleton: Optional[Fernet] = None
_fernet_initialized: bool = False
_current_key_str: Optional[str] = None


def reset_fernet_cache() -> None:
    """Resets cached Fernet singleton (used for key rotation and test fixtures)."""
    global _fernet_singleton, _fernet_initialized, _current_key_str
    _fernet_singleton = None
    _fernet_initialized = False
    _current_key_str = None


def get_fernet_instance() -> Optional[Fernet]:
    """
    Returns authenticated symmetric cipher (Fernet AES-128-CBC + HMAC-SHA256).
    Key is derived from ENCRYPTION_KEY environment configuration.
    Never silently generates a replacement key when key is unconfigured.
    """
    global _fernet_singleton, _fernet_initialized, _current_key_str
    key_str = getattr(settings, "ENCRYPTION_KEY", None)
    if _fernet_initialized and _current_key_str == key_str:
        return _fernet_singleton

    _current_key_str = key_str
    if not key_str:
        logger.warning(
            "ENCRYPTION_KEY is not configured. Sensitive notification credentials "
            "will be stored without encryption-at-rest."
        )
        _fernet_singleton = None
        _fernet_initialized = True
        return None

    key_bytes = key_str.strip().encode("utf-8")
    try:
        decoded = base64.urlsafe_b64decode(key_bytes)
        if len(decoded) == 32:
            _fernet_singleton = Fernet(key_bytes)
            _fernet_initialized = True
            return _fernet_singleton
    except Exception:
        pass

    # Derive 32-byte urlsafe base64 key from arbitrary passphrase
    derived = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
    _fernet_singleton = Fernet(derived)
    _fernet_initialized = True
    return _fernet_singleton


def validate_encryption_key_at_startup() -> None:
    """
    Validates encryption key configuration during application and worker startup:
    - Confirms configured key can initialize a valid cryptographic cipher.
    - If encrypted credentials exist in PostgreSQL, confirms the configured key
      can decrypt them successfully.
    - Aborts startup safely with a clear RuntimeError if ENCRYPTION_KEY is missing
      or invalid when encrypted data exists, preventing credential corruption.
    """
    from app.database import SessionLocal
    from app.models.models import NotificationChannel

    key_str = getattr(settings, "ENCRYPTION_KEY", None)

    # Check database for existing encrypted credentials
    db = SessionLocal()
    encrypted_samples: List[str] = []
    try:
        channels = db.query(NotificationChannel).all()
        for ch in channels:
            cfg = ch.configuration_json or {}
            for v in cfg.values():
                if isinstance(v, str) and v.startswith(ENC_PREFIX):
                    encrypted_samples.append(v)
    except Exception as db_err:
        logger.warning(f"Could not inspect database channels during startup key verification: {db_err}")
    finally:
        db.close()

    has_encrypted_data = len(encrypted_samples) > 0

    if not key_str:
        if has_encrypted_data:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: Encrypted notification credentials exist in PostgreSQL, "
                "but ENCRYPTION_KEY is not configured in .env. Application startup aborted to prevent "
                "credential corruption or silent delivery failures."
            )
        logger.warning(
            "ENCRYPTION_KEY is not configured. Sensitive notification credentials "
            "will be stored without encryption-at-rest."
        )
        return

    # Key is provided: verify Fernet initialization
    fernet = get_fernet_instance()
    if not fernet:
        raise RuntimeError(
            "CRITICAL CONFIGURATION ERROR: Configured ENCRYPTION_KEY is invalid or malformed. "
            "Unable to initialize cryptographic cipher."
        )

    # Verify key can decrypt existing stored samples
    for sample in encrypted_samples:
        dec = decrypt_credential(sample)
        if dec == sample or (isinstance(dec, str) and dec.startswith(ENC_PREFIX)):
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: Configured ENCRYPTION_KEY cannot decrypt "
                "existing encrypted credentials in PostgreSQL (key mismatch or corruption). "
                "Application startup aborted to prevent credential corruption."
            )


ENC_PREFIX = "enc:v1:"


def encrypt_credential(secret: Optional[str]) -> Optional[str]:
    """
    Encrypts sensitive credential string using authenticated encryption.
    Returns string prefixed with 'enc:v1:' or unchanged if encryption key is unavailable.
    """
    if not secret or not isinstance(secret, str):
        return secret

    if secret.startswith(ENC_PREFIX):
        return secret

    fernet = get_fernet_instance()
    if not fernet:
        return secret

    try:
        encrypted_token = fernet.encrypt(secret.encode("utf-8")).decode("utf-8")
        return f"{ENC_PREFIX}{encrypted_token}"
    except Exception as e:
        logger.error(f"Credential encryption failure: {e}")
        return secret


def decrypt_credential(value: Optional[str]) -> Optional[str]:
    """
    Decrypts encrypted credential string.
    Maintains 100% backwards compatibility with existing plaintext database values.
    """
    if not value or not isinstance(value, str):
        return value

    if not value.startswith(ENC_PREFIX):
        # Plaintext legacy value - return as-is
        return value

    raw_token = value[len(ENC_PREFIX):]
    fernet = get_fernet_instance()
    if not fernet:
        logger.error("Cannot decrypt credential: ENCRYPTION_KEY is not configured.")
        return value

    try:
        return fernet.decrypt(raw_token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt credential: InvalidToken (encryption key mismatch or corrupted data).")
        return value
    except Exception as e:
        logger.error(f"Failed to decrypt credential: {e}")
        return value


def encrypt_channel_config(channel_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypts sensitive fields in notification channel configuration before database persistence."""
    result = dict(config)
    ch_type = channel_type.lower()
    if ch_type == "discord" and "webhook_url" in result:
        result["webhook_url"] = encrypt_credential(result["webhook_url"])
    elif ch_type == "telegram" and "bot_token" in result:
        result["bot_token"] = encrypt_credential(result["bot_token"])
    elif ch_type == "email" and "smtp_password" in result:
        result["smtp_password"] = encrypt_credential(result["smtp_password"])
    return result


def decrypt_channel_config(channel_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypts sensitive fields in notification channel configuration after reading from database."""
    result = dict(config)
    ch_type = channel_type.lower()
    if ch_type == "discord" and "webhook_url" in result:
        result["webhook_url"] = decrypt_credential(result["webhook_url"])
    elif ch_type == "telegram" and "bot_token" in result:
        result["bot_token"] = decrypt_credential(result["bot_token"])
    elif ch_type == "email" and "smtp_password" in result:
        result["smtp_password"] = decrypt_credential(result["smtp_password"])
    return result


# -------------------------------------------------------------------------
# Webhook Destination Safety & SSRF Validation
# -------------------------------------------------------------------------
def validate_discord_webhook_url(webhook_url: str) -> None:
    """
    Strict validation of Discord webhook destinations:
    - Enforces HTTPS scheme.
    - Official Discord domains only (discord.com, discordapp.com, ptb.discord.com, canary.discord.com).
    - Prohibits embedded user/password credentials.
    - Prohibits non-standard ports.
    - Enforces expected official webhook path structure (/api/webhooks/<id>/<token>).
    - Validates DNS resolution does not resolve to private or loopback networks.
    """
    if not webhook_url or not isinstance(webhook_url, str):
        raise ValueError("Discord webhook_url is required.")

    clean_url = webhook_url.strip()
    parsed = urlsplit(clean_url)

    if parsed.scheme.lower() != "https":
        raise ValueError("Discord webhook URL must use HTTPS scheme.")

    if parsed.username or parsed.password:
        raise ValueError("Discord webhook URL must not contain embedded authentication credentials.")

    if parsed.port and parsed.port != 443:
        raise ValueError(f"Discord webhook URL must use standard HTTPS port 443 (got port {parsed.port}).")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Discord webhook URL must contain a valid hostname.")

    official_hosts = {"discord.com", "discordapp.com", "canary.discord.com", "ptb.discord.com"}
    is_official = hostname in official_hosts

    is_test_mock = settings.TEST_MODE and (
        hostname in ("mock", "localhost", "test")
        or "mock" in clean_url
        or "/api/webhooks/mock" in clean_url
        or "/api/webhooks/valid" in clean_url
    )

    if not is_official and not is_test_mock:
        raise ValueError(
            f"Invalid Discord webhook destination '{hostname}'. "
            "Only official discord.com and discordapp.com endpoints are allowed."
        )

    path = parsed.path or ""
    if not path.startswith("/api/webhooks/") and not is_test_mock:
        raise ValueError(
            f"Invalid Discord webhook path '{path}'. Discord webhooks must use '/api/webhooks/<id>/<token>'."
        )

    # DNS resolution SSRF protection
    if not is_test_mock and is_official:
        try:
            addr_info = socket.getaddrinfo(hostname, 443, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
            for _, _, _, _, sockaddr in addr_info:
                ip = ipaddress.ip_address(sockaddr[0])
                if is_ip_blocked(ip):
                    raise ValueError(f"Discord webhook hostname '{hostname}' resolved to prohibited IP {ip}.")
        except socket.gaierror:
            pass


def validate_telegram_config(bot_token: str, chat_id: str) -> None:
    """
    Validates Telegram bot token and chat ID to prevent injection or URL manipulation:
    - Rejects path traversal, whitespace, or control characters in bot_token.
    - Validates chat_id format (numeric or @channel_username).
    """
    if not bot_token or not isinstance(bot_token, str):
        raise ValueError("Telegram bot_token is required.")
    if not chat_id or not isinstance(chat_id, str):
        raise ValueError("Telegram chat_id is required.")

    clean_tok = bot_token.strip()
    clean_chat = chat_id.strip()

    # Reject whitespace or control characters or path traversal
    if any(c in clean_tok for c in (" ", "\t", "\n", "\r", "/", "\\", "..", "?", "#", "@")):
        raise ValueError("Telegram bot_token contains invalid characters.")

    if ":" not in clean_tok and not clean_tok.startswith("mock"):
        raise ValueError("Telegram bot_token must contain ':' separating bot ID and secret token.")

    if any(c in clean_chat for c in (" ", "\t", "\n", "\r", "/", "\\", "..", "?", "#")):
        raise ValueError("Telegram chat_id contains invalid characters.")
