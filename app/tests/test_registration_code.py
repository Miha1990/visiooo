import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import LegalAcceptance, PendingRegistration, User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class RegistrationCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.data = {'email': 'NEW@example.test', 'first_name': 'Анна', 'last_name': 'Иванова',
                     'password1': 'SomethingUnique-912!', 'password2': 'SomethingUnique-912!',
                     'consent': 'on', 'terms': 'on'}

    def start(self):
        response = self.client.post('/accounts/register', self.data)
        self.assertEqual(response.status_code, 303)
        return response

    def code(self):
        return re.search(r'Ваш код подтверждения: ([0-9]{6})', mail.outbox[-1].body)[1]

    def allow_resend(self):
        PendingRegistration.objects.update(last_sent_at=timezone.now() - timedelta(seconds=61))

    def test_only_valid_code_creates_account_and_consents(self):
        self.start()
        self.assertFalse(User.objects.exists())
        self.assertNotIn('_auth_user_id', self.client.session)
        pending = PendingRegistration.objects.get()
        self.assertTrue(check_password(self.data['password1'], pending.password))
        self.assertNotEqual(pending.code_digest, self.code())
        self.assertNotIn(self.code(), str(dict(self.client.session)))
        self.assertEqual(self.client.get('/accounts/registration-code').status_code, 200)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': self.code()})['Location'], '/app/cards')
        user = User.objects.get()
        self.assertEqual((user.email, user.first_name, user.last_name), ('new@example.test', 'Анна', 'Иванова'))
        self.assertTrue(user.check_password(self.data['password1']))
        self.assertIsNotNone(user.email_verified_at)
        self.assertEqual(user.workspace.membership_set.count(), 1)
        self.assertFalse(user.workspace.subscription.is_active)
        self.assertEqual(LegalAcceptance.objects.filter(user=user).count(), 2)
        self.assertFalse(PendingRegistration.objects.exists())
        self.assertIn('_auth_user_id', self.client.session)
        self.client.logout()
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': self.code()})['Location'], '/accounts/register')

    def test_session_binding_and_pending_password_cannot_login(self):
        self.start()
        other = Client()
        self.assertEqual(other.post('/accounts/registration-code', {'code': self.code()})['Location'], '/accounts/register')
        self.assertEqual(self.client.post('/accounts/login', {'username': self.data['email'],
                                                              'password': self.data['password1']}).status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_attempts_count_even_malformed_codes_and_resend_does_not_reset(self):
        self.start()
        for _ in range(5):
            self.assertEqual(self.client.post('/accounts/registration-code', {'code': 'bad'}).status_code, 422)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': self.code()}).status_code, 422)
        self.allow_resend()
        self.client.post('/accounts/registration-code/resend')
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(User.objects.exists())

    def test_expired_code_rejected_and_resend_replaces_code(self):
        with patch('accounts.registration.secrets.randbelow', return_value=123456):
            self.start()
        PendingRegistration.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': '123456'}).status_code, 422)
        self.client.post('/accounts/registration-code/resend')
        self.assertEqual(len(mail.outbox), 1)
        self.allow_resend()
        with patch('accounts.registration.secrets.randbelow', return_value=654321):
            self.client.post('/accounts/registration-code/resend')
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': '123456'}).status_code, 422)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': '654321'}).status_code, 303)
        self.assertEqual(User.objects.count(), 1)

    def test_mail_failure_creates_no_account_and_can_retry(self):
        with patch('accounts.registration.send_mail', side_effect=SMTPException('unavailable')):
            self.start()
        self.assertFalse(User.objects.exists())
        self.assertEqual(PendingRegistration.objects.get().code_digest, '')
        self.assertContains(self.client.get('/accounts/registration-code'), 'Не удалось отправить письмо')
        self.allow_resend()
        self.client.post('/accounts/registration-code/resend')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': self.code()}).status_code, 303)

    def test_email_send_quota_and_cannot_replace_another_browser(self):
        self.start()
        original_password = PendingRegistration.objects.get().password
        other = Client()
        data = dict(self.data, password1='AttackerPassword-234!', password2='AttackerPassword-234!')
        self.assertEqual(other.post('/accounts/register', data).status_code, 422)
        self.assertEqual(PendingRegistration.objects.get().password, original_password)
        for _ in range(6):
            self.allow_resend()
            self.client.post('/accounts/registration-code/resend')
        self.assertEqual(len(mail.outbox), 5)

    def test_consents_required_and_duplicate_email_rejected(self):
        self.assertEqual(self.client.post('/accounts/register', dict(self.data, consent='')).status_code, 422)
        self.assertFalse(PendingRegistration.objects.exists())
        User.objects.create_user('new@example.test', 'OtherPassword-531!')
        self.assertEqual(self.client.post('/accounts/register', self.data).status_code, 422)
        self.assertFalse(PendingRegistration.objects.exists())

    def test_code_and_resend_require_csrf_and_get_never_sends(self):
        self.start()
        secured = Client(enforce_csrf_checks=True)
        self.assertEqual(secured.post('/accounts/registration-code', {'code': self.code()}).status_code, 403)
        self.assertEqual(secured.post('/accounts/registration-code/resend').status_code, 403)
        self.assertEqual(self.client.get('/accounts/registration-code/resend').status_code, 405)
        self.assertIn('no-store', self.client.get('/accounts/registration-code')['Cache-Control'])
        self.assertEqual(len(mail.outbox), 1)
