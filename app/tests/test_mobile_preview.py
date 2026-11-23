from copy import deepcopy
from html.parser import HTMLParser
from io import StringIO
import json
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from cards.designs import DEFAULT, editor_design
from cards.models import CardTemplate
from cards.premium import PREMIUM_ID, definition
from cards.services import save_card, publish_card
from tests import test_visual_editor as fixtures


class Blocks(HTMLParser):
    def __init__(self):super().__init__();self.visible=set();self.hidden=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);key=attrs.get('data-design-block') or attrs.get('data-content-block')
        if key:(self.hidden if 'hidden' in attrs else self.visible).add(key)


class MobilePreviewTests(TestCase):
    setUp=fixtures.VisualEditorTests.setUp

    def test_empty_client_preview_matches_published_visibility_and_canvas_retains_slots(self):
        design=editor_design(deepcopy(DEFAULT));design['hidden']=[]
        save_card(self.user,self.card.pk,1,{**self.card.draft,'design':design})
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        preview=self.client.get(f'/app/cards/{self.card.pk}/edit')
        rendered=Blocks();rendered.feed(preview.content.decode())
        public=Blocks();public.feed(self.client.get(f'/c/{self.card.public_id}').content.decode())
        self.assertEqual(rendered.visible,public.visible)
        self.assertEqual(public.visible,{'identity','save'})
        self.assertTrue({'bio','contacts','socials','carousel','video','document','map','avatar','cover'}<=rendered.hidden)
        canvas=self.client.get(f'/app/cards/{self.card.pk}/design')
        layout=Blocks();layout.feed(canvas.content.decode())
        self.assertIn('video',layout.visible)
        self.assertContains(preview,'client-preview.js');self.assertContains(preview,'mobile.css')

    def test_json_save_before_upload_updates_version_and_reports_validation_and_conflicts(self):
        data={'name':'Новая подпись','draft_version':1,'template':'classic','accent':'#2457DB','links':''}
        url=f'/app/cards/{self.card.pk}/edit'
        response=self.client.post(url,data,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['version'],2)
        self.card.refresh_from_db();self.assertEqual(self.card.draft['name'],'Новая подпись')
        self.assertEqual(self.client.post(url,data,HTTP_ACCEPT='application/json').status_code,409)
        data.update(draft_version=2,name='')
        response=self.client.post(url,data,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,422);self.assertIn('name',response.json()['errors'])
        self.card.refresh_from_db();self.assertEqual(self.card.draft_version,2)

    def test_default_preset_updates_but_customer_snapshot_and_admin_edits_remain(self):
        old=json.loads((settings.BASE_DIR/'cards'/'presets'/'premium-v1.json').read_text(encoding='utf-8'))
        item=CardTemplate.objects.create(pk=PREMIUM_ID,name='Премиальный',draft=old,published=old,status='published',published_version=1)
        content={**self.card.draft,'design':old}
        # Example photo IDs are shared resources; the schema allows these design references.
        save_card(self.user,self.card.pk,1,content)
        call_command('install_premium_template',stdout=StringIO())
        item.refresh_from_db();self.card.refresh_from_db()
        self.assertEqual(item.draft,definition());self.assertEqual(item.published_version,2)
        self.assertEqual(self.card.draft['design'],old)
        item.draft['gap']=31;item.save()
        call_command('install_premium_template',stdout=StringIO())
        item.refresh_from_db();self.assertEqual(item.draft['gap'],31)
