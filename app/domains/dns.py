import hashlib
import ipaddress
import dns.exception
import dns.resolver
from django.conf import settings
from django.core.exceptions import ValidationError
from .validation import normalize_hostname


def ingress_addresses():
    addresses = []
    for value in settings.DOMAIN_IPV4.split(','):
        try:
            ip = ipaddress.IPv4Address(value.strip())
        except ValueError:
            continue
        if ip.is_global:
            addresses.append(str(ip))
    return addresses


def configured():
    return settings.CUSTOM_DOMAINS_ENABLED and bool(ingress_addresses())


def check_dns(binding):
    if not configured():
        return False
    host = normalize_hostname(binding.hostname)
    resolver = dns.resolver.Resolver()
    resolver.timeout = 2
    resolver.lifetime = 3
    try:
        txt = resolver.resolve(f'_myqr-verification.{host}.', 'TXT', search=False)
        values = [b''.join(record.strings).decode('utf-8', errors='replace') for record in txt]
        addresses = [str(record) for record in resolver.resolve(host + '.', 'A', search=False)]
        try:
            ipv6 = list(resolver.resolve(host + '.', 'AAAA', search=False))
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            ipv6 = []
        # Store only a hash; the reproducible value shown to the owner is not a login secret.
        expected = binding.verification_token_hash
        return bool(any(hashlib.sha256(value.encode()).hexdigest() == expected for value in values)
            and addresses and set(addresses) <= set(ingress_addresses()) and not ipv6)
    except (dns.exception.DNSException, OSError, ValidationError):
        return False
