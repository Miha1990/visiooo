from copy import deepcopy
from io import StringIO
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase
from cards.models import CardTemplate, TemplatePhoto
from cards.designs import BLOCKS, validate_design
from cards.premium import PREMIUM_ID, PHOTO_ASSETS, definition
from cards.services import publish_card
from tests import test_visual_editor as fixtures


class PremiumExampleTests(SimpleTestCase):
    def test_public_premium_example_shows_every_block_without_customer_data(self):
        response=self.client.get('/examples/premium')
        self.assertEqual(response.status_code,200)
        for key,_ in BLOCKS:self.assertContains(response,f'data-design-block="{key}"')
        for value in ('premium-example.pdf','avatar-static','data-social-mode="radial"',
                      'data-autoplay="false"','youtube-nocookie.com/embed/aqz-KE-bpKQ','Карта с адресом'):
            self.assertContains(response,value)
        self.assertContains(response,'<iframe',count=2);self.assertNotContains(response,'data-load-embed')
        self.assertContains(self.client.get('/examples/premium/contact.vcf'),'Елена Морозова')
        self.assertEqual(self.client.get('/examples/premium/qr.png').status_code,200)


class PremiumTemplateTests(TestCase):
    setUp=fixtures.VisualEditorTests.setUp

    def install(self):
        call_command('install_premium_template',stdout=StringIO())

    def test_installs_editable_published_template_and_keeps_admin_changes(self):
        self.install()
        item=CardTemplate.objects.get(pk=PREMIUM_ID)
        self.assertEqual(item.status,'published');self.assertEqual(item.published_version,1)
        self.assertEqual(set(item.published['blocks']),{key for key,_ in BLOCKS})
        validate_design(item.published)
        self.assertEqual(TemplatePhoto.objects.filter(pk__in=PHOTO_ASSETS).count(),3)
        response=self.client.get(f'/control/templates/{PREMIUM_ID}')
        self.assertContains(response,'data-visual-editor');self.assertContains(response,'premium-example.pdf')
        self.assertContains(response,'name="visual_design"')
        item.draft['caption']='Мой премиальный стиль';item.version=9;item.status='archived';item.save()
        self.install();item.refresh_from_db()
        self.assertEqual(item.version,9);self.assertEqual(item.status,'archived')
        self.assertEqual(item.draft['caption'],'Мой премиальный стиль')
        self.assertEqual(CardTemplate.objects.filter(pk=PREMIUM_ID).count(),1)

    def test_customer_receives_layout_and_empty_slots_without_fictional_data(self):
        self.install()
        response=self.client.get(f'/app/cards/{self.card.pk}/templates')
        self.assertContains(response,'Тихая роскошь');self.assertContains(response,'premium-example.pdf')
        response=self.client.post(f'/app/cards/{self.card.pk}/templates',{'template_id':PREMIUM_ID,'draft_version':1})
        self.assertEqual(response.status_code,303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['name'],'Новая визитка')
        self.assertFalse(self.card.draft['design']['hidden'])
        self.assertEqual(self.card.draft['design']['carousel']['photos'],[])
        for key in ('phone','email','video','document','map','avatarAssetId'):
            self.assertNotIn(key,self.card.draft)
        publish_card(self.user,self.card.pk,self.card.draft_version)
        response=self.client.get(f'/c/{self.card.public_id}')
        self.assertNotContains(response,'Елена Морозова');self.assertNotContains(response,'premium-example.pdf')
        self.assertNotContains(response,'data-design-block="video"')
        self.assertNotContains(response,'data-design-block="carousel"')
