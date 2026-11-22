"""Verify authenticated TLS SMTP, then configure Django without replacing other settings."""
from datetime import datetime, timezone
import os
from pathlib import Path
import smtplib
import ssl
import tempfile


def read_values(path):
    return dict(line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines()
                if line and not line.startswith('#') and '=' in line)


def main(root=None):
    root = root or Path(__file__).resolve().parents[2]
    values = read_values(root / 'ops/mail/.env')
    target = root / 'app/.env'
    original = target.read_text(encoding='utf-8')
    with smtplib.SMTP('mail.visiooo.ru', 587, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(values['SERVICE_MAILBOX_USER'], values['SERVICE_MAILBOX_PASSWORD'])
    updates = {
        'EMAIL_BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'EMAIL_HOST': 'mail.visiooo.ru', 'EMAIL_PORT': '587',
        'EMAIL_HOST_USER': values['SERVICE_MAILBOX_USER'],
        'EMAIL_HOST_PASSWORD': values['SERVICE_MAILBOX_PASSWORD'],
        'EMAIL_USE_TLS': 'true', 'EMAIL_USE_SSL': 'false',
        'DEFAULT_FROM_EMAIL': 'Визитка <no-reply@visiooo.ru>',
        'DATA_MAIL_PROVIDER': ('Собственный почтовый сервер оператора mail.visiooo.ru, '
            'размещённый у ООО «АЙТИ БАЗИС» (ООО «АЙТИБ»), ИНН 9719026854. '
            'Страна размещения почтового сервера — Российская Федерация'),
    }
    lines = []
    for line in original.splitlines():
        key = line.partition('=')[0]
        if key in updates:
            # Remove duplicates and append one authoritative value below.
            continue
        lines.append(line)
    lines.extend(f'{key}={value}' for key, value in updates.items())
    backup_dir = root / 'backups'
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    backup = backup_dir / ('app-env-before-mail-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+f'-{os.getpid()}.bak')
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(original)
    fd, temporary = tempfile.mkstemp(prefix='.env.mail-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write('\n'.join(lines)+'\n')
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('SMTP authentication with verified TLS succeeded; app/.env updated.')
    print('Recreate web, then test registration and delivery to an external mailbox.')


if __name__ == '__main__':
    main()
