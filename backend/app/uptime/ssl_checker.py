"""SSL certificate expiration checker."""

import ssl
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse


def check_ssl_cert(url: str, timeout: int = 10) -> dict | None:
    """Check SSL certificate for a given URL.

    Returns dict with issuer, subject, expiry info, or None if not HTTPS.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None

    hostname = parsed.hostname
    port = parsed.port or 443

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=timezone.utc
        )
        now = datetime.now(timezone.utc)
        days_until_expiry = (not_after - now).days

        # Extract issuer and subject
        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))

        return {
            "issuer": issuer.get("organizationName", issuer.get("commonName", "Unknown")),
            "subject": subject.get("commonName", "Unknown"),
            "not_before": not_before.isoformat(),
            "not_after": not_after.isoformat(),
            "days_until_expiry": days_until_expiry,
            "is_expired": days_until_expiry < 0,
            "is_expiring_soon": 0 <= days_until_expiry <= 30,
            "serial_number": cert.get("serialNumber"),
        }
    except Exception as e:
        return {
            "error": str(e),
            "issuer": None,
            "subject": None,
            "not_after": None,
            "days_until_expiry": None,
            "is_expired": None,
            "is_expiring_soon": None,
        }
