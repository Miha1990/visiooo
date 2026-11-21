import os
import shutil
from django.core.management.base import BaseCommand, CommandError
from domains.worker import process_one, inspect_active


class Command(BaseCommand):
    help = 'Host-side domain certificate worker; requires Linux Nginx/Certbot. Never run in the web process.'

    def add_arguments(self, parser):
        parser.add_argument('--renew', action='store_true')

    def handle(self, *args, **options):
        if os.name != 'posix' or any(not shutil.which(name) for name in ('nginx', 'certbot', 'systemctl')):
            raise CommandError('Нужен настроенный Linux-сервер с Nginx, Certbot и systemd.')
        import fcntl
        with open('/run/lock/myqr-domains.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            if options['renew']:
                inspect_active(renew=True)
            else:
                process_one()
                inspect_active()
