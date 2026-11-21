import ipaddress
import re
from urllib.parse import urlsplit
import idna
from django.conf import settings
from django.core.exceptions import ValidationError


def normalize_hostname(value):
    if not isinstance(value, str):
        raise ValidationError('Укажите домен без https://, порта и пути.')
    raw = value.strip().lower().rstrip('.')
    if not raw or re.search(r'[\\/:@?#%\s*]', raw):
        raise ValidationError('Укажите домен без https://, порта и пути.')
    try:
        host = idna.encode(raw, uts46=True, std3_rules=True).decode('ascii')
    except idna.IDNAError as error:
        raise ValidationError('Некорректное имя домена.') from error
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValidationError('Укажите домен, а не IP-адрес.')
    labels = host.split('.')
    if (len(host) > 253 or len(labels) < 2 or not re.fullmatch(r'[a-z][a-z0-9-]*', labels[-1])
            or labels[-1] in ('localhost', 'local', 'internal', 'test', 'invalid', 'example', 'arpa')
            or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)):
        raise ValidationError('Укажите публичный домен, например card.example.ru.')
    return host


def platform_conflict(host):
    hosts = [urlsplit(settings.PUBLIC_BASE_URL).hostname or '', *settings.ALLOWED_HOSTS]
    return any(host == base.lstrip('.') or host.endswith('.' + base.lstrip('.'))
               for base in hosts if base and base != '*')
