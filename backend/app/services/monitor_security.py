import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeMonitorTarget(ValueError):
    """Raised when a monitor URL could reach a non-public target."""


def _require_public_address(address: str) -> str:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise UnsafeMonitorTarget("Target resolved to an invalid address") from exc

    if not parsed.is_global:
        raise UnsafeMonitorTarget(
            "Private, loopback, link-local, and reserved targets are blocked"
        )
    return str(parsed)


def validate_monitor_target(url: str) -> tuple[str, ...]:
    """Validate scheme and every resolved IPv4/IPv6 target address."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise UnsafeMonitorTarget("Invalid monitor URL") from exc

    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeMonitorTarget("Only HTTP and HTTPS targets are allowed")
    if not parsed.hostname:
        raise UnsafeMonitorTarget("Monitor URL must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeMonitorTarget("Credentials in monitor URLs are not allowed")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeMonitorTarget("Localhost targets are blocked")

    target_port = port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        address_info = socket.getaddrinfo(
            hostname,
            target_port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeMonitorTarget("Target hostname could not be resolved") from exc

    resolved_addresses = {
        _require_public_address(info[4][0])
        for info in address_info
    }
    if not resolved_addresses:
        raise UnsafeMonitorTarget("Target hostname did not resolve")

    return tuple(sorted(resolved_addresses))
