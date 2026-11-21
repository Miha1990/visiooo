"""Create server secrets once, without printing or replacing existing secrets."""
import os
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parent.parent
    target = root / 'app' / '.env'
    password = secrets.token_urlsafe(48)
    values = {
        'SECRET_KEY': secrets.token_urlsafe(64),
        'POSTGRES_DB': 'visiooo',
        'POSTGRES_USER': 'visiooo',
        'POSTGRES_PASSWORD': password,
        'DATABASE_URL': f'postgresql://visiooo:{password}@db:5432/visiooo',
    }
    source = (root / 'app' / '.env.production.example').read_text(encoding='utf-8')
    lines = []
    for line in source.splitlines():
        key = line.partition('=')[0]
        lines.append(f'{key}={values[key]}' if key in values else line)
    # Exclusive creation preserves an existing installation, even on a second run.
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines) + '\n')
    print('Создан app/.env. Заполните SMTP и сведения оператора перед запуском продаж.')


if __name__ == '__main__':
    main()
