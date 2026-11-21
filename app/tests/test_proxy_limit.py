from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.middleware import SensitiveRequestLimit


class ProxyLimitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.middleware = SensitiveRequestLimit(lambda request: HttpResponse('ok'))

    def request(self, address):
        return self.middleware(self.factory.post('/accounts/login',
            REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP=address))

    @override_settings(TRUST_PROXY=True)
    def test_separate_visitors_behind_nginx(self):
        for _ in range(20):
            self.assertEqual(self.request('192.0.2.1').status_code, 200)
        self.assertEqual(self.request('192.0.2.1').status_code, 429)
        self.assertEqual(self.request('192.0.2.2').status_code, 200)

    @override_settings(TRUST_PROXY=False)
    def test_untrusted_headers_cannot_bypass_limit(self):
        for index in range(20):
            self.assertEqual(self.request(f'192.0.2.{index}').status_code, 200)
        self.assertEqual(self.request('192.0.2.99').status_code, 429)

    @override_settings(TRUST_PROXY=True)
    def test_invalid_header_falls_back_to_peer(self):
        for _ in range(20):
            self.request('invalid')
        self.assertEqual(self.request('invalid').status_code, 429)
