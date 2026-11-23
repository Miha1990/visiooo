from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

from django.http import Http404
from django.test import SimpleTestCase, RequestFactory, override_settings

from config import seo


@override_settings(ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
                   PUBLIC_BASE_URL='https://visiooo.ru')
class DiscoveryTests(SimpleTestCase):
    def test_discovery_exposes_only_public_service_pages(self):
        robots = self.client.get('/robots.txt')
        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, 'Sitemap: https://visiooo.ru/sitemap.xml')
        self.assertContains(robots, 'Disallow: /accounts/')
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.content)
        locations = [node.text for node in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertIn('https://visiooo.ru/pricing', locations)
        self.assertEqual(len(locations), 9)
        self.assertFalse(any('/c/' in url or '/app/' in url or '/accounts/' in url for url in locations))
        for path in ['/robots.txt', '/sitemap.xml', '/favicon.ico']:
            self.assertEqual(self.client.head(path).status_code, 200)
            self.assertEqual(self.client.post(path).status_code, 405)

    def test_marketing_preview_has_absolute_urls_and_no_tracking_query(self):
        response = self.client.get('/pricing?utm_source=message')
        self.assertContains(response, 'property="og:url" content="https://visiooo.ru/pricing"')
        self.assertContains(response, 'property="og:image" content="https://visiooo.ru/static/brand/share-cover.png"')
        self.assertContains(response, 'name="twitter:card" content="summary_large_image"')
        self.assertContains(response, 'name="robots" content="index,follow"')
        self.assertNotContains(response, 'utm_source=')
        self.assertContains(self.client.get('/accounts/login'), 'name="robots" content="noindex,nofollow"')
        icon = self.client.get('/favicon.ico')
        self.assertEqual(icon['Content-Type'], 'image/x-icon')
        self.assertEqual(b''.join(icon.streaming_content)[:4], b'\x00\x00\x01\x00')

    def test_card_preview_uses_published_snapshot_and_escapes_content(self):
        content = {'name': 'Анна <script>', 'title': 'Дизайнер', 'template': 'classic',
                   'accent': '#2457db', 'avatarAssetId': '277f8751-c7b2-4872-830f-6d41df004f83'}
        card = SimpleNamespace(public_id='owner', draft={'name': 'SECRET DRAFT', 'avatarAssetId': 'private-photo'},
                               published_revision=SimpleNamespace(content=content, publication_conditions=''))
        with patch('cards.views.public_card', return_value=card), patch('cards.analytics.record_view'):
            response = self.client.get('/c/owner', secure=True)
        self.assertContains(response, 'property="og:title" content="Анна &lt;script&gt; — визитка"')
        self.assertContains(response, 'property="og:image" content="https://testserver/c/owner/assets/277f8751-c7b2-4872-830f-6d41df004f83"')
        self.assertContains(response, 'name="robots" content="noindex,nofollow"')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertNotContains(response, 'private-photo')
        self.assertNotContains(response, 'SECRET DRAFT')
        with patch('cards.views.public_card', side_effect=Http404):
            self.assertEqual(self.client.get('/c/owner').status_code, 404)

    def test_custom_domain_keeps_its_url_and_does_not_list_customer_cards(self):
        request = RequestFactory().get('/?source=share', secure=True)
        request.domain_binding = SimpleNamespace()
        data = seo.metadata(request)
        self.assertEqual(data['url'], 'https://testserver/')
        self.assertFalse(data['indexable'])
        self.assertNotIn(b'Sitemap:', seo.robots(request).content)
        root = ElementTree.fromstring(seo.sitemap(request).content)
        self.assertEqual(len(root), 0)

    def test_examples_have_their_own_preview(self):
        response = self.client.get('/examples/designer')
        self.assertContains(response, 'property="og:title" content="Александра Ким — пример визитки"')
        self.assertContains(response, 'property="og:image" content="https://visiooo.ru/static/examples/designer-cover.webp"')
        self.assertContains(response, 'name="robots" content="noindex,nofollow"')
