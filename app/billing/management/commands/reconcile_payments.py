from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from billing.models import Payment
from billing.services import refresh, enabled
from billing.gateway import GatewayError


class Command(BaseCommand):
    help = 'Проверить недавние платежи и возвраты в ЮКассе; безопасно запускать повторно.'

    def handle(self, *args, **options):
        if not enabled():
            self.stderr.write('Оплата не настроена.')
            return
        records = Payment.objects.exclude(provider_id=None).filter(created_at__gte=timezone.now() - timedelta(days=400))
        for payment in records.iterator():
            try:
                refresh(payment)
                self.stdout.write(f'{payment.pk}: проверен')
            except GatewayError:
                self.stderr.write(f'{payment.pk}: проверка отложена')
