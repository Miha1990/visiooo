from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import AnalyticsConsent


class Command(BaseCommand):
    help = 'Удалить подтверждения выбора аналитики старше трёх лет.'

    def handle(self, *args, **options):
        removed, _ = AnalyticsConsent.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=3 * 365)).delete()
        self.stdout.write(f'Удалено записей выбора аналитики: {removed}')
