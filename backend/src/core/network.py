import ipaddress

TRUSTED_PROXIES = {
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
}


def is_trusted_proxy(ip: str) -> bool:
    """Check whether an IP address belongs to a trusted proxy network."""
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in TRUSTED_PROXIES)
    except ValueError:
        return False
