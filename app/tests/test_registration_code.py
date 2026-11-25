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

    def test_email_send_quota_and_other_browser_cannot_replace_during_cooldown(self):
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

    def test_repeat_form_within_minute_continues_with_current_code(self):
        self.start()
        code = self.code()
        for _ in range(3):
            self.assertEqual(self.client.post('/accounts/register', self.data)['Location'], '/accounts/registration-code')
        self.assertEqual(len(mail.outbox), 1)
        response = self.client.get('/accounts/registration-code')
        self.assertContains(response, 'Код уже отправлен')
        self.assertNotContains(response, 'Регистрация на эту почту уже начата')
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': code}).status_code, 303)
        self.assertEqual(User.objects.count(), 1)

    def test_resend_timer_uses_server_deadline_on_refresh_and_failed_confirmation(self):
        self.start()
        response=self.client.get('/accounts/registration-code')
        self.assertGreater(response.context['code_retry_seconds'],0)
        self.assertLessEqual(response.context['code_retry_seconds'],60)
        self.assertContains(response,'data-code-request-button disabled')
        self.assertContains(self.client.get('/accounts/register'),'data-retry-email="new@example.test"')
        self.client.post('/accounts/registration-code/resend')
        self.assertEqual(len(mail.outbox),1)
        PendingRegistration.objects.update(last_sent_at=timezone.now()-timedelta(seconds=31))
        response=self.client.post('/accounts/registration-code',{'code':'bad'})
        self.assertGreater(response.context['code_retry_seconds'],0)
        self.assertLessEqual(response.context['code_retry_seconds'],29)
        self.allow_resend()
        response=self.client.get('/accounts/registration-code')
        self.assertEqual(response.context['code_retry_seconds'],0)
        self.assertNotContains(response,'data-code-request-button disabled')

    def test_hourly_limit_is_reflected_in_timer_without_more_emails(self):
        self.start()
        PendingRegistration.objects.update(send_count=5)
        response=self.client.get('/accounts/registration-code')
        self.assertGreater(response.context['code_retry_seconds'],3500)
        self.client.post('/accounts/registration-code/resend')
        self.assertEqual(len(mail.outbox),1)

    def test_repeat_form_after_minute_sends_new_code(self):
        with patch('accounts.registration.secrets.randbelow', return_value=123456):
            self.start()
        self.allow_resend()
        with patch('accounts.registration.secrets.randbelow', return_value=654321):
            self.assertEqual(self.client.post('/accounts/register', self.data).status_code, 303)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': '123456'}).status_code, 422)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': '654321'}).status_code, 303)

    def test_new_browser_can_restart_after_minute_but_needs_fresh_code(self):
        with patch('accounts.registration.secrets.randbelow', return_value=123456):
            self.start()
        previous_token = self.client.session['pending_registration']
        other = Client()
        changed = dict(self.data, password1='UpdatedPassword-239!', password2='UpdatedPassword-239!')
        blocked = other.post('/accounts/register', changed)
        self.assertContains(blocked, 'через минуту', status_code=422)
        self.assertEqual(PendingRegistration.objects.get().browser_token.hex, previous_token.replace('-', ''))
        self.allow_resend()
        with patch('accounts.registration.secrets.randbelow', return_value=654321):
            self.assertEqual(other.post('/accounts/register', changed).status_code, 303)
        self.assertNotEqual(other.session['pending_registration'], previous_token)
        self.assertEqual(other.post('/accounts/registration-code', {'code': '123456'}).status_code, 422)
        self.assertFalse(User.objects.exists())
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': '654321'})['Location'], '/accounts/register')
        self.assertEqual(other.post('/accounts/registration-code', {'code': '654321'}).status_code, 303)
        self.assertTrue(User.objects.get().check_password(changed['password1']))

    def test_restarting_in_another_browser_does_not_reset_guess_limit(self):
        self.start()
        for _ in range(5):
            self.client.post('/accounts/registration-code', {'code': 'bad'})
        self.allow_resend()
        self.assertEqual(Client().post('/accounts/register', self.data).status_code, 422)
        self.assertEqual(PendingRegistration.objects.get().attempts, 5)
        self.assertEqual(len(mail.outbox), 1)

    def test_repeat_form_recovers_from_mail_failure(self):
        with patch('accounts.registration.send_mail', side_effect=SMTPException('unavailable')):
            self.start()
        self.allow_resend()
        self.assertEqual(self.client.post('/accounts/register', self.data).status_code, 303)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': self.code()}).status_code, 303)

    def test_expired_rate_window_allows_new_code_after_wrong_attempts(self):
        self.start()
        PendingRegistration.objects.update(attempts=5, send_count=5,
            window_started_at=timezone.now() - timedelta(hours=2))
        self.allow_resend()
        self.client.post('/accounts/registration-code/resend')
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(PendingRegistration.objects.get().attempts, 0)
        self.assertEqual(self.client.post('/accounts/registration-code', {'code': self.code()}).status_code, 303)

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
