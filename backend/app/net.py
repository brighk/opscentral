"""Guards for outbound HTTP requests to user-supplied URLs.

Tenants can make the server send requests (runbook webhooks, Jira/ServiceNow
integrations). Without a guard, they could reach internal services or cloud
metadata endpoints (SSRF). Self-hosted installs that need to call internal
systems can opt out with OC_ALLOW_PRIVATE_NETWORK_TARGETS=true.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from app.config import settings


class UnsafeURLError(ValueError):
    pass


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_outbound_url(url: str) -> None:
    """Raise UnsafeURLError unless `url` is http(s) and resolves only to public addresses.

    Note: this checks resolution at call time; a hostile DNS server could still answer
    differently when the request is made (DNS rebinding). Callers must not follow
    redirects, since a redirect target is not re-validated.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("URL must use http or https")
    if not parsed.hostname:
        raise UnsafeURLError("URL has no host")

    if settings.ALLOW_PRIVATE_NETWORK_TARGETS:
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Could not resolve host {parsed.hostname!r}") from e

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not _is_public(ip):
            raise UnsafeURLError(
                f"Host {parsed.hostname!r} resolves to a non-public address ({ip}); "
                "set OC_ALLOW_PRIVATE_NETWORK_TARGETS=true to allow this on a self-hosted install"
            )


async def validate_outbound_url_async(url: str) -> None:
    """Async wrapper: DNS resolution is blocking, so run it in a thread."""
    await asyncio.to_thread(validate_outbound_url, url)
