from copy import deepcopy
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from cards.forms import CardForm
from cards.models import CardTemplate
from cards.designs import DEFAULT, editor_design
from cards.services import save_card, publish_card
from tests import test_visual_editor as fixtures
from tests.test_images import photo


class ClientContentTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def customer(self):
        self.user.is_staff=False;self.user.is_superuser=False;self.user.save()

    def layout(self):
        design=editor_design(deepcopy(DEFAULT));design['hidden']=[]
        save_card(self.user,self.card.pk,self.card.draft_version,{**self.card.draft,'design':design})
        self.card.refresh_from_db()
        return design

    def post_media(self,operation,**extra):
        self.card.refresh_from_db()
        return self.client.post(f'/app/cards/{self.card.pk}/content-media',{'draft_version':self.card.draft_version,'operation':operation,**extra})

    def form_data(self,**extra):
        self.card.refresh_from_db()
        return {'draft_version':self.card.draft_version,'name':'Клиент','template':'design' if self.card.draft.get('design') else 'classic',
                'accent':self.card.draft['accent'],'links':'',**extra}

    def test_customer_cannot_open_or_post_visual_editor(self):
        self.customer()
        response=self.client.get(f'/app/cards/{self.card.pk}/edit')
        self.assertNotContains(response,'Визуальный редактор:')
        self.assertContains(response,'Карусель товаров и фотографий')
        self.assertContains(response,'name="video_url"')
        self.assertEqual(self.client.get(self.url).status_code,403)
        self.assertEqual(self.client.post(self.url,{'content':'{}','draft_version':1}).status_code,403)

    def test_client_form_preserves_layout_and_ignores_forged_design(self):
        design=self.layout();self.customer()
        response=self.client.post(f'/app/cards/{self.card.pk}/edit',self.form_data(video_url='https://youtu.be/dQw4w9WgXcQ',
            video_title='Моя работа',map_address='Ростов-на-Дону, Зорге 27',pdf_label='Скачать прайс',design='{"blocks":[]}',accent='#000000'))
        self.assertEqual(response.status_code,303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['design'],design)
        self.assertEqual(self.card.draft['accent'],design['accent'])
        self.assertEqual(self.card.draft['video']['title'],'Моя работа')
        self.assertEqual(self.card.draft['map']['address'],'Ростов-на-Дону, Зорге 27')
        self.assertEqual(self.card.draft['document']['label'],'Скачать прайс')

    def test_empty_blocks_omitted_from_public_design(self):
        self.layout();publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get(f'/c/{self.card.public_id}')
        for key in ('cover','avatar','bio','contacts','socials','carousel','video','document','map'):
            self.assertNotContains(response,f'data-design-block="{key}"')
        self.assertNotContains(response,'data-preview="title"');self.assertNotContains(response,'Добавьте PDF')
        self.assertNotContains(response,'Показать карту');self.assertContains(response,'data-design-block="identity"')

    def test_customer_uploads_removes_and_reorders_gallery_and_pdf(self):
        self.layout();self.customer()
        for _ in range(2):self.assertEqual(self.post_media('gallery',file=photo()).status_code,302)
        self.card.refresh_from_db();ids=self.card.draft['galleryAssetIds'][:]
        self.post_media('earlier',asset_id=ids[1]);self.card.refresh_from_db()
        self.assertEqual(self.card.draft['galleryAssetIds'],ids[::-1])
        self.post_media('remove_photo',asset_id=ids[0]);self.card.refresh_from_db()
        self.assertEqual(self.card.draft['galleryAssetIds'],[ids[1]])
        self.post_media('pdf',file=SimpleUploadedFile('price.pdf',b'%PDF-1.4\n%%EOF'))
        self.card.refresh_from_db();self.assertTrue(self.card.draft['document']['assetId'])
        publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response,'data-design-block="carousel"');self.assertContains(response,'data-design-block="document"')
        self.post_media('remove_pdf');self.card.refresh_from_db();self.assertNotIn('assetId',self.card.draft['document'])

    def test_templates_control_available_content_blocks(self):
        design=self.layout();design['hidden']=['video','map','document','carousel']
        save_card(self.user,self.card.pk,self.card.draft_version,{**self.card.draft,'design':design})
        self.customer();response=self.client.get(f'/app/cards/{self.card.pk}/edit')
        self.assertNotContains(response,'name="video_url"');self.assertNotContains(response,'Карусель товаров и фотографий')
        count=self.card.draft_version
        self.post_media('gallery',file=photo());self.card.refresh_from_db()
        self.assertNotIn('galleryAssetIds',self.card.draft)

    def test_builtin_templates_show_only_filled_media(self):
        self.customer()
        self.client.post(f'/app/cards/{self.card.pk}/edit',self.form_data(video_url='https://youtu.be/dQw4w9WgXcQ'))
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response,'Смотреть видео');self.assertNotContains(response,'Показать карту')
        self.assertNotContains(response,'Добавьте фотографии');self.assertNotContains(response,'class="contact-cover"')
