from copy import deepcopy
import json
from django.conf import settings
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from cards.builtin_templates import EXAMPLE_TEMPLATES, definition
from cards.examples import example_cards
from cards.models import CardTemplate
from tests import test_visual_editor as fixtures


class BuiltinTemplateTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def test_stock_examples_upgrade_without_rewriting_customer_snapshot(self):
        originals=json.loads((settings.BASE_DIR/'cards'/'presets'/'website-examples-v1.json').read_text(encoding='utf-8'))
        pk=EXAMPLE_TEMPLATES['designer'][0];old=originals['designer']
        item=CardTemplate.objects.create(pk=pk,name='Старое оформление',draft=old,published=old,status='published',published_version=1)
        from cards.services import save_card
        save_card(self.user,self.card.pk,self.card.draft_version,{**self.card.draft,'design':old})
        call_command('install_premium_template',stdout=StringIO());item.refresh_from_db();self.card.refresh_from_db()
        self.assertEqual(item.published,definition('designer'));self.assertEqual(item.published_version,2)
        self.assertEqual(self.card.draft['design'],old)
        call_command('install_premium_template',stdout=StringIO());item.refresh_from_db();self.assertEqual(item.published_version,2)

    def test_examples_and_catalogue_share_editable_layouts(self):
        call_command('install_premium_template', stdout=StringIO())
        for example in example_cards():
            slug = example['slug']
            pk, name, _ = EXAMPLE_TEMPLATES[slug]
            item = CardTemplate.objects.get(pk=pk)
            self.assertEqual(item.published, example['content']['design'])
            self.assertEqual(item.published, definition(slug))
            self.assertContains(self.client.get(f'/app/cards/{self.card.pk}/templates'), name)
            self.assertContains(self.client.get(f'/control/templates/{pk}'), 'data-visual-editor')

    def test_install_preserves_admin_edits_and_customer_apply_preserves_content(self):
        call_command('install_premium_template', stdout=StringIO())
        pk = EXAMPLE_TEMPLATES['photographer'][0]
        item = CardTemplate.objects.get(pk=pk)
        item.draft = deepcopy(item.draft)
        item.draft['gap'] = 29
        item.save()
        call_command('install_premium_template', stdout=StringIO())
        item.refresh_from_db()
        self.assertEqual(item.draft['gap'], 29)
        from cards.services import save_card
        save_card(self.user,self.card.pk,self.card.draft_version,{**self.card.draft,'layout':{'order':['contacts','identity']}})
        self.card.refresh_from_db()
        original = deepcopy(self.card.draft)
        response = self.client.post(f'/app/cards/{self.card.pk}/templates', {
            'template_id': pk, 'draft_version': self.card.draft_version})
        self.assertEqual(response.status_code, 303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['name'], original['name'])
        self.assertEqual(self.card.draft['design']['sourceId'], pk)
        self.assertNotIn('layout', self.card.draft)
        self.assertNotIn('example', str(self.card.draft))
