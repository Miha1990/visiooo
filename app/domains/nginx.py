"""Host-side Nginx/Certbot adapter, based on SPCh's isolated vhost workflow."""
import os
import logging
import re
import socket
import ssl
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from django.conf import settings
from .validation import normalize_hostname

MARKER = '# Managed by myQR domains.\n'
NGINX_DIR = Path('/etc/nginx/conf.d')
WEBROOT = Path('/var/lib/myqr-acme')
CERT_DIR = Path('/etc/letsencrypt/live')
logger = logging.getLogger(__name__)


def command(args, timeout=30):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        logger.error('%s failed: %s', args[0], (result.stdout + '\n' + result.stderr)[-4000:])
        # Neither certificate errors nor command output containing server paths go to customers.
        raise RuntimeError(f'{args[0]} завершился с ошибкой; проверьте журнал на сервере.')
    return result.stdout


def validate(binding):
    identifier = str(uuid.UUID(str(binding.pk)))
    host = normalize_hostname(binding.hostname)
    if host != binding.hostname:
        raise ValueError('Hostname must already be normalized')
    port = settings.DOMAIN_UPSTREAM_PORT
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('Invalid upstream port')
    return identifier, host, port


def config(binding, https=False):
    identifier, host, port = validate(binding)
    static_root = str(settings.STATIC_ROOT)
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', static_root) or '..' in PurePosixPath(static_root).parts:
        raise ValueError('STATIC_ROOT must be an absolute Linux path without whitespace')
    challenge = f'location ^~ /.well-known/acme-challenge/ {{ root {WEBROOT.as_posix()}; try_files $uri =404; }}\n'
    proxy = f'''location /static/ {{ alias {static_root}/; }}
location / {{
    proxy_pass http://127.0.0.1:{port};
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $remote_addr;
}}
'''
    body = MARKER + f'server {{\nlisten 80;\nserver_name {host};\naccess_log off;\nclient_max_body_size 6m;\n' + challenge
    body += ('location / { return 301 https://$host$request_uri; }\n' if https else proxy) + '}\n'
    if https:
        certificate = (CERT_DIR / f'myqr-{identifier}').as_posix()
        body += f'''server {{
listen 443 ssl;
server_name {host};
access_log off;
client_max_body_size 6m;
ssl_certificate {certificate}/fullchain.pem;
ssl_certificate_key {certificate}/privkey.pem;
ssl_protocols TLSv1.2 TLSv1.3;
{proxy}}}
'''
    return body


def conflicting_config(dump, hostname, managed_path):
    chunks, filename, lines = [], '', []
    for line in dump.splitlines():
        if line.startswith('# configuration file '):
            chunks.append((filename, '\n'.join(lines)))
            filename = line[len('# configuration file '):].rstrip(':')
            lines = []
        else:
            lines.append(line.split('#', 1)[0])
    chunks.append((filename, '\n'.join(lines)))
    for filename, body in chunks:
        if filename == Path(managed_path).as_posix():
            continue
        for group in re.findall(r'\bserver_name\s+([^;]+);', body):
            for name in group.lower().split():
                if (name == hostname or (name.startswith('*.') and hostname.endswith(name[1:]))
                    or (name.startswith('.') and (hostname == name[1:] or hostname.endswith(name)))):
                    return True
    return False


def atomic_write(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix='.myqr-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_config(path, content):
    if path.is_symlink():
        raise RuntimeError('Конфликт конфигурации Nginx.')
    previous = path.read_text(encoding='utf-8') if path.exists() else None
    if previous is not None and not previous.startswith(MARKER):
        raise RuntimeError('Конфигурация принадлежит другому сервису.')
    if previous == content:
        return
    atomic_write(path, content)
    try:
        command(['nginx', '-t'])
        command(['systemctl', 'reload', 'nginx'])
    except Exception:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, previous)
        command(['nginx', '-t'])
        command(['systemctl', 'reload', 'nginx'])
        raise


def certificate_expiry(host):
    normalize_hostname(host)
    # The only TLS connection is to local ingress. Certificate name + CA are verified.
    with socket.create_connection(('127.0.0.1', 443), timeout=8) as raw:
        with ssl.create_default_context().wrap_socket(raw, server_hostname=host) as connection:
            timestamp = ssl.cert_time_to_seconds(connection.getpeercert()['notAfter'])
    return datetime.fromtimestamp(timestamp, timezone.utc)


def provision(binding):
    identifier, host, _ = validate(binding)
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', settings.DOMAIN_ACME_EMAIL):
        raise RuntimeError('Настройте DOMAIN_ACME_EMAIL на сервере.')
    path = NGINX_DIR / f'myqr-domain-{identifier}.conf'
    if path.is_symlink() or (path.exists() and not path.read_text(encoding='utf-8').startswith(MARKER)):
        raise RuntimeError('Нельзя перезаписать чужую конфигурацию Nginx.')
    if conflicting_config(command(['nginx', '-T']), host, path):
        raise RuntimeError('Домен уже настроен в другом virtual host Nginx. Требуется администратор.')
    (WEBROOT / '.well-known' / 'acme-challenge').mkdir(parents=True, exist_ok=True)
    if not path.exists():
        apply_config(path, config(binding))
    command(['certbot', 'certonly', '--webroot', '--webroot-path', str(WEBROOT),
        '--cert-name', f'myqr-{identifier}', '-d', host, '--email', settings.DOMAIN_ACME_EMAIL,
        '--agree-tos', '--non-interactive', '--keep-until-expiring'], timeout=360)
    apply_config(path, config(binding, https=True))
    for attempt in range(5):
        try:
            return certificate_expiry(host)
        except (OSError, ssl.SSLError, KeyError, ValueError):
            if attempt == 4:
                raise
            time.sleep(1)


def renew(binding):
    identifier, host, _ = validate(binding)
    try:
        command(['certbot', 'renew', '--cert-name', f'myqr-{identifier}', '--non-interactive'], timeout=360)
        command(['nginx', '-t'])
        command(['systemctl', 'reload', 'nginx'])
    except (RuntimeError, subprocess.TimeoutExpired):
        logger.exception('Certificate renewal requires attention for %s', host)
        # A transient ACME/Certbot lock failure must not hide a still-valid site.
    return certificate_expiry(host)
