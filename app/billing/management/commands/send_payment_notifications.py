import time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from billing.notifications import send_pending


class Command(BaseCommand):
    help = 'Отправить владельцу уведомления о подтверждённых оплатах; --watch запускает постоянную обработку.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true')

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            sent, failed = send_pending()
            if sent or failed or not options['watch']:
                self.stdout.write(f'Передано почтовому серверу: {sent}; отложено после ошибки: {failed}.')
            if not options['watch']:
                return
            time.sleep(15)
