import socket
import ipaddress
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from typing import Tuple, Optional
from app.config import settings


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
