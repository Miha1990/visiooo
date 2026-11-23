from copy import deepcopy
from html.parser import HTMLParser
from django.test import TestCase, Client
from cards.designs import DEFAULT
from cards.forms import CardForm
from cards.services import save_card, publish_card
from tests import test_visual_editor as fixtures


class ButtonText(HTMLParser):
    def __init__(self):
        super().__init__(); self.href = None; self.labels = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href'); self.labels.setdefault(self.href, '')

    def handle_endtag(self, tag):
        if tag == 'a': self.href = None

    def handle_data(self, value):
        if self.href: self.labels[self.href] += value


class ContactButtonLabelsTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def data(self):
        form = CardForm.for_card(self.card)
        return {name: form[name].value() or '' for name in form.fields}

    def test_labels_are_independent_from_destinations_in_both_layouts(self):
        for design in (None, deepcopy(DEFAULT)):
            for label in ('Позвонить', '89289091817'):
                content = deepcopy(self.card.draft)
                if design: content['design'] = design
                else: content.pop('design', None)
                save_card(self.user, self.card.pk, self.card.draft_version, content)
                self.card.refresh_from_db()
                data = self.data(); data.update(phone='8 (928) 909-18-17', phone_label=label,
                    email='customer@example.test', email_label='Написать письмо')
                form = CardForm.for_card(self.card, data)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.content['phone'], '+79289091817')
                save_card(self.user, self.card.pk, self.card.draft_version, form.content)
                self.card.refresh_from_db(); publish_card(self.user, self.card.pk, self.card.draft_version)
                self.card.refresh_from_db()
                response = Client().get(f'/c/{self.card.public_id}')
                parsed = ButtonText(); parsed.feed(response.content.decode())
                self.assertEqual(parsed.labels['tel:+79289091817'], label)
                self.assertEqual(parsed.labels['mailto:customer@example.test'], 'Написать письмо')
                vcard = self.client.get(f'/c/{self.card.public_id}/contact.vcf').content.decode()
                self.assertIn('TEL;TYPE=CELL:+79289091817', vcard)

    def test_editor_groups_fields_and_keeps_label_when_number_is_empty(self):
        response = self.client.get(f'/app/cards/{self.card.pk}/edit')
        for value in ('Кнопка «Телефон»', 'Текст на кнопке', 'Номер телефона', 'data-button-example="phone"'):
            self.assertContains(response, value)
        data = self.data(); data.update(phone_label='Записаться', phone='')
        form = CardForm.for_card(self.card, data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.content['phoneLabel'], 'Записаться')
        self.assertNotIn('phone', form.content)

    def test_invalid_number_and_oversized_caption_are_rejected(self):
        for phone, label, error in [('not-a-number', 'Call', 'phone'), ('89289091817', 'x'*81, 'phone_label')]:
            data = self.data(); data.update(phone=phone, phone_label=label)
            form = CardForm.for_card(self.card, data)
            self.assertFalse(form.is_valid()); self.assertIn(error, form.errors)

    def test_label_is_escaped_on_public_page(self):
        data = self.data(); data.update(phone='89289091817', phone_label='<script>alert(1)</script>')
        form = CardForm.for_card(self.card, data); self.assertTrue(form.is_valid(), form.errors)
        save_card(self.user, self.card.pk, self.card.draft_version, form.content)
        self.card.refresh_from_db(); publish_card(self.user, self.card.pk, self.card.draft_version)
        response = Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_bare_domains_work_for_website_socials_and_additional_buttons(self):
        data = self.data(); data.update(website='google.com', social_telegram='t.me/example',
            links='Поиск | google.com\nПортфолио | example.com:8443/work')
        form = CardForm.for_card(self.card, data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.content['website'], 'https://google.com')
        self.assertEqual(form.content['socials']['telegram'], 'https://t.me/example')
        self.assertEqual(form.content['links'][0]['url'], 'https://google.com')
        self.assertEqual(form.content['links'][1]['url'], 'https://example.com:8443/work')
        self.assertEqual(form.fields['website'].widget.input_type, 'text')
        self.assertEqual(form.fields['social_telegram'].widget.input_type, 'text')

    def test_unsafe_urls_are_rejected_when_short_addresses_are_enabled(self):
        for url in ('javascript:alert(1)', 'ftp://example.com', 'https://user:password@example.com', 'not a domain'):
            data = self.data(); data['links'] = 'Открыть | ' + url
            self.assertFalse(CardForm.for_card(self.card, data).is_valid(), url)
