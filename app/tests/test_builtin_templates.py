from copy import deepcopy
from io import StringIO
from django.core.management import call_command
from django.test import TestCase
from cards.builtin_templates import EXAMPLE_TEMPLATES, definition
from cards.examples import example_cards
from cards.models import CardTemplate
from tests import test_visual_editor as fixtures


class BuiltinTemplateTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

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
        original = deepcopy(self.card.draft)
        response = self.client.post(f'/app/cards/{self.card.pk}/templates', {
            'template_id': pk, 'draft_version': self.card.draft_version})
        self.assertEqual(response.status_code, 303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['name'], original['name'])
        self.assertEqual(self.card.draft['design']['sourceId'], pk)
        self.assertNotIn('example', str(self.card.draft))
