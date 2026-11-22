"""Prepare two mail accounts and secrets on the server. Never replace existing data."""
import os
from pathlib import Path
import secrets
import subprocess


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(value)


def main(root=None):
    root = root or Path(__file__).resolve().parents[2]
    directory = root / 'mail-data'
    config = directory / 'config'
    target = root / 'ops/mail/.env'
    files = [target, config / 'postfix-accounts.cf', config / 'postfix-virtual.cf']
    if any(path.exists() for path in files):
        raise SystemExit('Mail configuration already exists; refusing to replace accounts or secrets.')
    users = {'support@visiooo.ru': secrets.token_urlsafe(32),
             'no-reply@visiooo.ru': secrets.token_urlsafe(32)}
    accounts = []
    for address, password in users.items():
        result = subprocess.run(['openssl', 'passwd', '-6', '-stdin'], input=password+'\n',
                                text=True, capture_output=True, check=True)
        hashed = result.stdout.strip()
        if not hashed.startswith('$6$') or '\n' in hashed:
            raise SystemExit('Unexpected password hash format')
        accounts.append(f'{address}|{{SHA512-CRYPT}}{hashed}')
    directory.mkdir(mode=0o700, exist_ok=True)
    config.mkdir(mode=0o700, exist_ok=True)
    contents = [
        f'MAIL_DB_PASSWORD={secrets.token_urlsafe(48)}',
        f'ROUNDCUBE_DES_KEY={secrets.token_urlsafe(18)}',
        'WEBMAIL_PORT=18082',
        f'MAILBOX_USER=support@visiooo.ru',
        f'MAILBOX_PASSWORD={users["support@visiooo.ru"]}',
        'SERVICE_MAILBOX_USER=no-reply@visiooo.ru',
        f'SERVICE_MAILBOX_PASSWORD={users["no-reply@visiooo.ru"]}',
    ]
    write_private(target, '\n'.join(contents)+'\n')
    write_private(files[1], '\n'.join(accounts)+'\n')
    write_private(files[2], 'postmaster@visiooo.ru support@visiooo.ru\nabuse@visiooo.ru support@visiooo.ru\n')
    print('Mail accounts prepared. Credentials: ops/mail/.env (server only).')
    print('Do not send this file or passwords to chat or GitHub.')


if __name__ == '__main__':
    main()
