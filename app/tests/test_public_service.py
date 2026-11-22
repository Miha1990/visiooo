from django.test import SimpleTestCase, override_settings

from billing.services import PRICES


@override_settings(ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PUBLIC_BASE_URL='https://visiooo.ru')
class PublicServiceTests(SimpleTestCase):
    def test_information_is_public_without_account_or_database(self):
        for url in ['/', '/pricing', '/contacts', '/legal/offer', '/legal/privacy']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '615308640848')
                self.assertContains(response, 'href="/contacts"')

    def test_public_price_matches_checkout_and_access_is_explained(self):
        response = self.client.get('/contacts')
        self.assertContains(response, f'{int(PRICES["month"])} ₽')
        annual = f'{int(PRICES["year"]):,}'.replace(',', ' ')
        self.assertContains(response, f'{annual} ₽')
        self.assertTemplateUsed(response, 'service_access.html')
        for url in ['/', '/pricing']:
            self.assertTemplateUsed(self.client.get(url), 'service_access.html')

    @override_settings(OPERATOR_ADDRESS='123456, <Адрес для обращений>')
    def test_contacts_and_offer_use_same_escaped_address(self):
        for url in ['/contacts', '/legal/offer']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, '123456, &lt;Адрес для обращений&gt;')
                self.assertNotContains(response, '<Адрес для обращений>')
