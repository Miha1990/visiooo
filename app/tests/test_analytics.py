import hashlib
from datetime import timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import AnalyticsConsent
from config.analytics import COOKIE


@override_settings(ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   YANDEX_METRIKA_ID='123456', PUBLIC_BASE_URL='https://visiooo.ru')
class AnalyticsTests(TestCase):
    def setUp(self):
        cache.clear()

    def choose(self, choice='granted', **kwargs):
        return self.client.post('/analytics/consent', {'choice': choice, 'version': '2026-11-22.1', **kwargs})

    def test_opt_in_stores_exact_separate_document_and_signed_browser_receipt(self):
        self.assertIsNone(self.client.get('/analytics/consent').json()['choice'])
        self.assertEqual(AnalyticsConsent.objects.count(), 0)
        response = self.choose()
        self.assertEqual(response.status_code, 200)
        event = AnalyticsConsent.objects.get()
        self.assertEqual(event.choice, 'granted')
        self.assertEqual(event.counter_id, '123456')
        self.assertIn('своей волей', event.document_text)
        self.assertEqual(hashlib.sha256(event.document_text.encode()).hexdigest(), event.document_sha256)
        self.assertTrue(response.cookies[COOKIE]['httponly'])
        self.assertEqual(response.cookies[COOKIE]['samesite'], 'Lax')
        self.assertEqual(int(response.cookies[COOKIE]['max-age']), 180 * 86400)
        self.assertEqual(self.client.get('/analytics/consent').json()['choice'], 'granted')

    def test_refusal_and_withdrawal_do_not_depend_on_account(self):
        self.choose('denied')
        self.assertEqual(self.client.get('/analytics/consent').json()['choice'], 'denied')
        self.choose()
        previous = AnalyticsConsent.objects.latest('created_at')
        self.choose('denied')
        event = AnalyticsConsent.objects.latest('created_at')
        self.assertEqual(event.choice, 'withdrawn')
        self.assertEqual(event.previous_receipt, previous.pk)
        self.assertEqual(self.client.get('/analytics/consent').json()['choice'], 'withdrawn')
        self.assertIsNone(Client().get('/analytics/consent').json()['choice'])

    def test_tampering_and_changed_counter_or_document_require_new_consent(self):
        self.choose()
        with override_settings(YANDEX_METRIKA_ID='654321'):
            self.assertIsNone(self.client.get('/analytics/consent').json()['choice'])
        with override_settings(ANALYTICS_CONSENT_VERSION='next'):
            self.assertIsNone(self.client.get('/analytics/consent').json()['choice'])
        with override_settings(OPERATOR_EMAIL='new@example.test'):
            self.assertIsNone(self.client.get('/analytics/consent').json()['choice'])
        self.client.cookies[COOKIE] = self.client.cookies[COOKIE].value + 'tampered'
        self.assertIsNone(self.client.get('/analytics/consent').json()['choice'])
        self.assertEqual(AnalyticsConsent.objects.count(), 1)

    def test_unsafe_requests_are_rejected_and_state_is_not_cached(self):
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf_client.post('/analytics/consent', {'choice': 'granted'}).status_code, 403)
        state = csrf_client.get('/analytics/consent')
        token = state.json()['csrf_token']
        self.assertIn('no-store', state['Cache-Control'])
        self.assertEqual(csrf_client.post('/analytics/consent', {'choice': 'granted',
            'version': '2026-11-22.1'}, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(self.choose('surprise').status_code, 400)
        self.assertEqual(self.choose(version='old').status_code, 409)

    @override_settings(YANDEX_METRIKA_ID='')
    def test_unconfigured_counter_stays_off_even_after_opt_in(self):
        self.assertEqual(self.choose().json(), {'enabled': False, 'choice': None})
        self.assertEqual(AnalyticsConsent.objects.count(), 0)
        self.assertNotContains(self.client.get('/'), 'analytics-config')
        self.assertContains(self.client.get('/legal/cookies'), 'Яндекс Метрика не активирована')

    def test_only_marketing_pages_are_eligible_and_no_external_script_in_html(self):
        for path in ['/', '/pricing', '/contacts']:
            response = self.client.get(path)
            self.assertContains(response, '"eligible": true')
            self.assertNotContains(response, 'src="https://mc.yandex.ru')
            self.assertContains(response, 'data-analytics-choice="denied"')
        for path in ['/accounts/login', '/accounts/register', '/legal/cookies', '/legal/privacy']:
            self.assertContains(self.client.get(path), '"eligible": false')
        self.assertNotContains(self.client.get('/examples/designer'), 'analytics-config')

    def test_daily_cleanup_removes_only_expired_evidence(self):
        self.choose()
        old = AnalyticsConsent.objects.get()
        AnalyticsConsent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=1096))
        self.choose('denied')
        call_command('cleanup_analytics_consents', stdout=StringIO())
        self.assertFalse(AnalyticsConsent.objects.filter(pk=old.pk).exists())
        self.assertEqual(AnalyticsConsent.objects.count(), 1)
