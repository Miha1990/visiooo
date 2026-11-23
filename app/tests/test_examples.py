from unittest.mock import patch
from uuid import UUID
from types import SimpleNamespace

from django.http import HttpResponse
from django.templatetags.static import static
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings


@override_settings(ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PUBLIC_BASE_URL='https://cards.example')
class ExampleTests(SimpleTestCase):
    def test_examples_work_without_customer_data_or_login(self):
        for slug in ['designer', 'photographer', 'property']:
            with self.subTest(slug=slug):
                response = self.client.get(f'/examples/{slug}')
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'cards/fragment.html')
                self.assertContains(response, static(f'examples/{slug}-portrait.webp'))
                self.assertContains(response, 'Демонстрационная визитка')
                self.assertContains(response, f'/examples/{slug}/contact.vcf')

    def test_only_fixed_examples_are_exposed_and_get_is_required(self):
        for suffix in ['', '/qr.png', '/contact.vcf']:
            self.assertEqual(self.client.get('/examples/customer-secret'+suffix).status_code, 404)
            self.assertEqual(self.client.post('/examples/designer'+suffix).status_code, 405)

    def test_qr_and_contact_point_to_same_example(self):
        with patch('cards.views.qr_response', return_value=HttpResponse(b'png')) as render_qr:
            self.assertEqual(self.client.get('/examples/designer/qr.png').status_code, 200)
            render_qr.assert_called_once_with('https://cards.example/examples/designer', 'example-qr.png')
        response = self.client.get('/examples/designer/contact.vcf')
        self.assertEqual(response.status_code, 200)
        self.assertIn('inline;', response['Content-Disposition'])
        self.assertIn('BEGIN:VCARD\r\n', response.content.decode())
        self.assertIn('URL:https://cards.example/examples/designer\r\n', response.content.decode())
        self.assertIn('FN:Александра Ким', response.content.decode())

    def test_regular_cards_keep_their_scoped_asset_and_share_routes(self):
        asset = '277f8751-c7b2-4872-830f-6d41df004f83'
        card = SimpleNamespace(pk=UUID('55a6de1c-98a5-4110-8b27-1f08aa85d34f'), public_id='customer-card')
        content = {'name': 'Владелец', 'template': 'classic', 'accent': '#2457db',
                   'avatarAssetId': asset, 'headerAssetId': asset, 'backgroundAssetId': asset}
        public = render_to_string('cards/fragment.html', {'card': card, 'content': content})
        preview = render_to_string('cards/fragment.html', {'card': card, 'content': content, 'preview': True})
        self.assertIn(f'/c/customer-card/assets/{asset}', public)
        self.assertNotIn('/c/customer-card/qr.png', public)
        self.assertIn('/c/customer-card/contact.vcf', public)
        self.assertIn(f'/app/cards/{card.pk}/assets/{asset}', preview)
        self.assertNotIn('/static/examples/', public + preview)
