import os
import secrets
from datetime import timedelta
from urllib.parse import urlsplit
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from accounts.models import User
from workspaces.models import Workspace, Membership
from billing.models import Subscription
from cards.models import Card
from cards.services import publish_card


class Command(BaseCommand):
    help = 'Create a local-only verified account with a test subscription and card.'

    def add_arguments(self, parser):
        parser.add_argument('--email', default='demo@example.test')
        parser.add_argument('--password', default=None)

    @transaction.atomic
    def handle(self, *args, **options):
        if (not settings.DEBUG or os.getenv('ENVIRONMENT', 'local') != 'local'
                or urlsplit(settings.PUBLIC_BASE_URL).hostname not in ('localhost', '127.0.0.1', '::1')):
            raise CommandError('Demo fixtures are allowed only in a local DEBUG environment.')
        email = options['email'].strip().lower()
        password = options['password'] or secrets.token_urlsafe(16)
        user, created = User.objects.get_or_create(email=email)
        if not created:
            raise CommandError('Account already exists; refusing to overwrite its password or data.')
        user.set_password(password)
        user.email_verified_at = timezone.now()
        user.save()
        workspace = Workspace.objects.create(owner=user, name='Демо-пространство')
        Membership.objects.create(user=user, workspace=workspace)
        Subscription.objects.create(workspace=workspace, status='active', paid_until=timezone.now() + timedelta(days=30))
        card = Card.objects.create(workspace=workspace, draft={
            'schemaVersion': 1, 'name': 'Анна Иванова', 'title': 'Бренд-дизайнер', 'company': 'Студия Форма',
            'bio': 'Помогаю хорошим идеям стать заметными брендами.\nБуду рада новым проектам и знакомствам.',
            'phone': '+79991234567', 'email': 'anna@example.test', 'website': 'https://example.com',
            'template': 'classic', 'accent': '#2457DB',
            'links': [{'label': 'Портфолио', 'url': 'https://example.com/portfolio'}]})
        publish_card(user, card.pk, card.draft_version)
        self.stdout.write(self.style.SUCCESS(f'Local demo created. Email: {email}\nPassword: {password}'))
        self.stdout.write(f'Card: {settings.PUBLIC_BASE_URL}/c/{card.public_id}')
        self.stdout.write(f'Editor: {settings.PUBLIC_BASE_URL}/app/cards/{card.pk}/edit')
        self.stdout.write(f'QR: {settings.PUBLIC_BASE_URL}/app/cards/{card.pk}/qr.png')
