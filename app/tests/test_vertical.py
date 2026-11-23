import hashlib
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from accounts.models import User, EmailToken
from accounts.views import issue_verification
from billing.models import Subscription
from workspaces.models import Workspace, Membership
from cards.models import Card
from cards.services import create_card, save_card, publish_card, Conflict
from cards.validation import validate_content
from cards.vcard import render_vcard


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PUBLIC_BASE_URL='http://127.0.0.1:8000')
class VerticalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('owner@example.test', 'SecureTest-543!')
        self.user.email_verified_at = timezone.now()
        self.user.save()
        self.workspace = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.workspace)
        self.sub = Subscription.objects.create(workspace=self.workspace, status='active',
                                               paid_until=timezone.now() + timedelta(days=30))
        self.card = create_card(self.user)
        self.content = {'schemaVersion': 1, 'name': 'Анна; Иванова, Дизайнер', 'template': 'classic',
                        'accent': '#2457DB', 'bio': 'Первая строка\nВторая строка',
                        'phone': '+79991234567', 'email': 'public@example.test', 'links': []}
        save_card(self.user, self.card.pk, 1, self.content)
        self.card.refresh_from_db()
        self.client.force_login(self.user)

    def publish(self):
        return publish_card(self.user, self.card.pk, self.card.draft_version)

    def public_paths(self):
        root = f'/c/{self.card.public_id}'
        return [root, root + '/contact.vcf']

    def test_registration_atomic_workspace_and_password(self):
        self.client.logout()
        response = self.client.post('/accounts/register', {'email': 'New@Example.test',
            'password1': 'SomethingUnique-912!', 'password2': 'SomethingUnique-912!', 'consent': 'on', 'terms': 'on'})
        self.assertEqual(response.status_code, 303)
        self.assertFalse(User.objects.filter(email='new@example.test').exists())
        import re
        code = re.search(r'\b([0-9]{6})\b', mail.outbox[-1].body)[1]
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': code}).status_code, 303)
        user = User.objects.get(email='new@example.test')
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(user.check_password('SomethingUnique-912!'))
        self.assertEqual(Workspace.objects.filter(owner=user).count(), 1)
        self.assertEqual(Membership.objects.filter(user=user).count(), 1)
        self.assertFalse(user.workspace.subscription.is_active)
        self.assertEqual(len(mail.outbox), 1)

    def test_case_insensitive_unique_email(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('OWNER@EXAMPLE.TEST', 'Whatever-987')

    def test_login_email_normalization_and_safe_next(self):
        self.client.logout()
        response = self.client.post('/accounts/login?next=https://evil.example', {
            'username': 'OWNER@EXAMPLE.TEST', 'password': 'SecureTest-543!'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['Location'], '/app/cards')

    def test_owner_pages_render(self):
        for path in ['/', '/pricing', '/app/cards', f'/app/cards/{self.card.pk}/edit', '/health/live', '/health/ready']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_admin_custom_user_forms_render(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        for path in ['/admin/accounts/user/add/', f'/admin/accounts/user/{self.user.pk}/change/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_public_text_is_escaped(self):
        save_card(self.user, self.card.pk, self.card.draft_version,
                  dict(self.content, name='<script>alert(1)</script>'))
        self.card.refresh_from_db()
        self.publish()
        response = self.client.get(self.public_paths()[0])
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_draft_not_public(self):
        for path in self.public_paths():
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_snapshot_and_stable_qr(self):
        self.publish()
        url = self.public_paths()[0]
        before = self.client.get(f'/app/cards/{self.card.pk}/qr.png').content
        changed = dict(self.content, name='Другое имя')
        save_card(self.user, self.card.pk, self.card.draft_version, changed)
        response = self.client.get(url)
        self.assertContains(response, 'Анна; Иванова, Дизайнер')
        self.assertNotContains(response, 'Другое имя')
        self.assertIn('no-store', response['Cache-Control'])
        self.card.refresh_from_db()
        self.publish()
        self.assertContains(self.client.get(url), 'Другое имя')
        after = self.client.get(f'/app/cards/{self.card.pk}/qr.png').content
        self.assertEqual(before, after)
        self.assertEqual(Image.open(BytesIO(after)).format, 'PNG')

    def test_unpublish_and_delete_close_all_public_paths(self):
        self.publish()
        self.assertEqual(self.client.get(f'/app/cards/{self.card.pk}/unpublish').status_code, 405)
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/unpublish').status_code, 303)
        for path in self.public_paths():
            self.assertEqual(self.client.get(path).status_code, 404)
        self.publish()
        self.client.post(f'/app/cards/{self.card.pk}/delete')
        for path in self.public_paths():
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(Card.objects.get(pk=self.card.pk).status, 'deleted')
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/publish').status_code, 404)

    def test_block_and_expiry_override_publication(self):
        self.publish()
        self.sub.paid_until = timezone.now() - timedelta(seconds=1)
        self.sub.save()
        for path in self.public_paths():
            self.assertEqual(self.client.get(path).status_code, 404)
        self.sub.paid_until = timezone.now() + timedelta(days=1)
        self.sub.save()
        self.assertEqual(self.client.get(self.public_paths()[0]).status_code, 200)
        Card.objects.filter(pk=self.card.pk).update(blocked=True)
        for path in self.public_paths():
            self.assertEqual(self.client.get(path).status_code, 404)
        with self.assertRaises(ValidationError):
            self.publish()

    def test_unverified_cannot_publish(self):
        self.user.email_verified_at = None
        self.user.save()
        with self.assertRaises(ValidationError):
            self.publish()

    def test_unpaid_cannot_publish(self):
        self.sub.status = 'pending'
        self.sub.save()
        with self.assertRaises(ValidationError):
            self.publish()

    def test_ownership_all_routes(self):
        other = User.objects.create_user('other@example.test', 'OtherSecret-912!')
        workspace = Workspace.objects.create(owner=other)
        Membership.objects.create(user=other, workspace=workspace)
        Subscription.objects.create(workspace=workspace)
        self.client.force_login(other)
        for suffix, method in [('edit', 'get'), ('edit', 'post'), ('qr.png', 'get'),
                               ('publish', 'post'), ('unpublish', 'post'), ('delete', 'post')]:
            with self.subTest(suffix=suffix, method=method):
                response = getattr(self.client, method)(f'/app/cards/{self.card.pk}/{suffix}')
                self.assertEqual(response.status_code, 404)

    def test_stale_save_and_publish_do_not_overwrite(self):
        save_card(self.user, self.card.pk, self.card.draft_version, dict(self.content, name='Новая версия'))
        with self.assertRaises(Conflict):
            save_card(self.user, self.card.pk, self.card.draft_version, self.content)
        with self.assertRaises(Conflict):
            self.publish()
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['name'], 'Новая версия')

    def test_schema_and_url_validation(self):
        invalid = [dict(self.content, website='javascript:alert(1)'),
                   dict(self.content, email='not-an-email'), dict(self.content, phone='123'),
                   dict(self.content, name='   '), dict(self.content, accent='#ffffff'),
                   dict(self.content, workspace_id=str(self.workspace.pk)),
                   dict(self.content, links=[{'label': 'X', 'url': 'https://u:p@example.com'}]),
                   dict(self.content, links=[{'label': 'X', 'url': 'https://example.com'}] * 11)]
        for content in invalid:
            with self.subTest(content=content), self.assertRaises(ValidationError):
                validate_content(content)

    def test_form_retains_invalid_values(self):
        response = self.client.post(f'/app/cards/{self.card.pk}/edit', dict(self.content,
            draft_version=self.card.draft_version, links='broken link', name='Введённое имя'))
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, 'Введённое имя', status_code=422)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft, self.content)

    def test_quota(self):
        create_card(self.user)
        create_card(self.user)
        with self.assertRaises(ValidationError):
            create_card(self.user)
        self.sub.status = 'pending'
        self.sub.save()
        with self.assertRaises(ValidationError):
            create_card(self.user)

    def test_vcard_private_data_escaping_folding(self):
        self.publish()
        response = self.client.get(self.public_paths()[1])
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.user.email.encode(), response.content)
        text = response.content.decode('utf-8')
        self.assertIn('FN:Анна\\; Иванова\\, Дизайнер\r\n', text)
        self.assertIn('NOTE:Первая строка\\nВторая строка', text)
        long = render_vcard(dict(self.content, name='Я' * 100), 'https://example.com')
        for line in long.split(b'\r\n'):
            self.assertLessEqual(len(line), 75)
            line.decode('utf-8')

    def test_verify_get_does_not_consume_and_post_is_single_use(self):
        with patch('accounts.views.secrets.token_urlsafe', return_value='test-verify-token'):
            issue_verification(self.user)
        record = EmailToken.objects.get(digest=hashlib.sha256(b'test-verify-token').hexdigest())
        url = '/accounts/verify/test-verify-token'
        self.assertEqual(self.client.get(url).status_code, 200)
        record.refresh_from_db()
        self.assertIsNone(record.used_at)
        self.assertEqual(self.client.post(url).status_code, 303)
        self.assertEqual(self.client.post(url).status_code, 400)

    def test_expired_verify_token(self):
        EmailToken.objects.create(user=self.user, digest=hashlib.sha256(b'expired').hexdigest(),
                                   expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post('/accounts/verify/expired').status_code, 400)

    def test_csrf_and_post_only(self):
        from django.test import Client
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post(f'/app/cards/{self.card.pk}/delete').status_code, 403)
        self.assertEqual(browser.get(f'/app/cards/{self.card.pk}/delete').status_code, 200)
        self.assertEqual(browser.get('/accounts/logout').status_code, 405)

    def test_demo_command_disabled_in_production(self):
        from django.core.management.base import CommandError
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command('seed_demo', stdout=BytesIO())

    def test_unknown_host_rejected(self):
        self.assertEqual(self.client.get('/', HTTP_HOST='evil.example').status_code, 400)

    def test_auth_rate_limit(self):
        self.client.logout()
        for _ in range(20):
            self.client.post('/accounts/login', {'username': 'wrong@example.test', 'password': 'bad'})
        self.assertEqual(self.client.post('/accounts/login').status_code, 429)
