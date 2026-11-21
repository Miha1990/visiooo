from datetime import timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from billing.models import Subscription
from workspaces.models import Workspace, Membership
from cards.forms import CardForm
from cards.services import create_card, save_card, publish_card
from cards.socials import SOCIAL_NETWORKS, social_links
from cards.validation import validate_content


class SocialLinksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('social@example.test', 'SocialPassword-294!', email_verified_at=timezone.now())
        self.workspace = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.workspace)
        Subscription.objects.create(workspace=self.workspace, status='active', paid_until=timezone.now() + timedelta(days=1))
        self.card = create_card(self.user)
        self.client.force_login(self.user)
        self.socials = {key: placeholder for key, _, placeholder in SOCIAL_NETWORKS}

    def test_all_socials_and_website_round_trip(self):
        data = dict(name='Анна', template='classic', accent='#2457DB', draft_version=1, links='',
                    website='https://example.com')
        data.update({f'social_{key}': url for key, url in self.socials.items()})
        form = CardForm.for_card(self.card, data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.content['socials'], self.socials)
        save_card(self.user, self.card.pk, 1, form.content)
        self.card.refresh_from_db()
        edit_form = CardForm.for_card(self.card)
        for key, url in self.socials.items():
            self.assertEqual(edit_form[f'social_{key}'].value(), url)
        self.assertEqual(len(social_links(self.card.draft)), 8)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        for template in ('classic', 'minimal', 'profile'):
            self.card.refresh_from_db()
            save_card(self.user, self.card.pk, self.card.draft_version, dict(self.card.draft, template=template))
            self.card.refresh_from_db()
            publish_card(self.user, self.card.pk, self.card.draft_version)
            response = self.client.get(reverse('public', args=[self.card.public_id]))
            for key, label, url in SOCIAL_NETWORKS:
                self.assertContains(response, f'social-{key}')
                self.assertContains(response, f'href="{url}"')
                self.assertContains(response, f'/static/icons/{key}.svg')
            self.assertContains(response, 'icons/website.svg')
            self.assertContains(response, 'href="https://example.com"', count=1)

    def test_social_edits_require_republication(self):
        save_card(self.user, self.card.pk, 1, dict(self.card.draft, socials={'telegram': 'https://t.me/before'}))
        self.card.refresh_from_db()
        publish_card(self.user, self.card.pk, self.card.draft_version)
        save_card(self.user, self.card.pk, self.card.draft_version,
                  dict(self.card.draft, socials={'telegram': 'https://t.me/after'}))
        response = self.client.get(reverse('public', args=[self.card.public_id]))
        self.assertContains(response, 'https://t.me/before')
        self.assertNotContains(response, 'https://t.me/after')

    def test_empty_optional_fields_and_legacy_website(self):
        content = dict(self.card.draft, website='https://example.com')
        validate_content(content)
        self.assertEqual(social_links(content), [{'key': 'website', 'label': 'Сайт', 'url': 'https://example.com'}])
        form = CardForm.for_card(self.card, {'name': 'Анна', 'template': 'minimal', 'accent': '#2457DB',
            'draft_version': 1, 'links': ''})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn('socials', form.content)
        self.assertNotIn('website', form.content)

    def test_social_url_validation_and_unknown_keys(self):
        for socials in ({'telegram': 'javascript:alert(1)'}, {'vk': 'https://user:pass@vk.com/name'},
                        {'instagram': 'https://example.com/\n'}, {'unsupported': 'https://example.com'},
                        {'max': ''}, {'avito': ['https://example.com']}):
            with self.subTest(socials=socials), self.assertRaises(ValidationError):
                validate_content(dict(self.card.draft, socials=socials))
        response = self.client.post(reverse('edit', args=[self.card.pk]), {
            'draft_version': 1, 'name': 'Введённое имя', 'template': 'classic', 'accent': '#2457DB',
            'social_instagram': 'javascript:alert(1)', 'links': ''})
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, 'Введённое имя', status_code=422)
        self.card.refresh_from_db()
        self.assertNotIn('socials', self.card.draft)

    def test_editor_fields_and_local_svg_assets(self):
        response = self.client.get(reverse('edit', args=[self.card.pk]))
        self.assertContains(response, 'Соцсети и сайт')
        for key, label, _ in SOCIAL_NETWORKS:
            self.assertContains(response, f'name="social_{key}"')
        for key in [key for key, _, _ in SOCIAL_NETWORKS] + ['website']:
            root = ET.fromstring((settings.BASE_DIR / 'static' / 'icons' / f'{key}.svg').read_text(encoding='utf-8'))
            for node in root.iter():
                self.assertNotIn(node.tag.split('}')[-1], ('script', 'foreignObject', 'image'))
                self.assertFalse(any(attr.lower().startswith('on') for attr in node.attrib))
