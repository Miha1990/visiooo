from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings, Client
from django.utils import timezone

from accounts.models import User, PasswordResetToken
from accounts.password_reset import issue_password_reset


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PUBLIC_BASE_URL='http://127.0.0.1:8000')
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('reset@example.test', 'OriginalPassword-438!')
        self.token = 'fixed-test-reset-token'
        with patch('accounts.password_reset.secrets.token_urlsafe', return_value=self.token):
            issue_password_reset(self.user)
        self.url = '/accounts/password-reset/' + self.token
        self.passwords = {'new_password1': 'A-new-unique-password-294!', 'new_password2': 'A-new-unique-password-294!'}

    def test_request_is_neutral_and_email_uses_configured_origin(self):
        mail.outbox.clear()
        known = self.client.post('/accounts/password-reset', {'email': 'RESET@EXAMPLE.TEST'}, HTTP_HOST='testserver')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('http://127.0.0.1:8000/accounts/password-reset/', mail.outbox[0].body)
        unknown = self.client.post('/accounts/password-reset', {'email': 'missing@example.test'})
        self.assertEqual((known.status_code, known['Location']), (unknown.status_code, unknown['Location']))
        self.assertEqual(len(mail.outbox), 1)

    def test_email_failure_remains_neutral(self):
        with patch('accounts.password_reset.send_mail', side_effect=SMTPException('unavailable')):
            with self.assertLogs('accounts.password_reset', level='WARNING'):
                response = self.client.post('/accounts/password-reset', {'email': self.user.email})
        self.assertEqual(response.status_code, 303)

    def test_get_does_not_consume_or_change_password(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertIsNone(PasswordResetToken.objects.get().used_at)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OriginalPassword-438!'))
        record = PasswordResetToken.objects.get()
        self.assertNotEqual(record.digest, self.token)
        self.assertEqual(len(record.digest), 64)

    def test_reset_single_use_and_login_with_new_password(self):
        self.assertEqual(self.client.post(self.url, self.passwords).status_code, 303)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.passwords['new_password1']))
        self.assertFalse(self.user.check_password('OriginalPassword-438!'))
        self.assertEqual(self.client.post(self.url, self.passwords).status_code, 400)
        self.assertTrue(self.client.login(email=self.user.email, password=self.passwords['new_password1']))

    def test_expired_and_inactive_rejected(self):
        PasswordResetToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(self.url).status_code, 400)
        PasswordResetToken.objects.update(expires_at=timezone.now() + timedelta(hours=1))
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.post(self.url, self.passwords).status_code, 400)

    def test_password_change_invalidates_all_other_tokens_and_sessions(self):
        with patch('accounts.password_reset.secrets.token_urlsafe', return_value='second-token'):
            issue_password_reset(self.user)
        self.client.force_login(self.user)
        self.client.post(self.url, self.passwords)
        self.assertEqual(self.client.get('/accounts/password-reset/second-token').status_code, 400)
        self.assertEqual(self.client.get('/app/cards').status_code, 302)

    def test_weak_and_mismatched_passwords_leave_token_usable(self):
        for fields in [{'new_password1': '123', 'new_password2': '123'},
                       dict(self.passwords, new_password2='different')]:
            self.assertEqual(self.client.post(self.url, fields).status_code, 422)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertIsNone(PasswordResetToken.objects.get().used_at)

    def test_csrf_required(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, self.passwords).status_code, 403)
        self.assertEqual(client.post('/accounts/password-reset', {'email': self.user.email}).status_code, 403)

    def test_unknown_token_and_pages(self):
        self.assertEqual(self.client.get('/accounts/password-reset/unknown').status_code, 400)
        self.assertEqual(self.client.get('/accounts/password-reset').status_code, 200)
        self.assertEqual(self.client.get('/accounts/password-reset/sent').status_code, 200)
        self.assertEqual(self.client.post('/accounts/password-reset', {'email': 'invalid'}).status_code, 422)
