import json
from copy import deepcopy
from django.test import TestCase, Client
from cards.forms import CardForm
from cards.designs import DEFAULT
from cards.services import publish_card, save_card
from cards.button_builder import clean_buttons, initial_buttons
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from tests import test_visual_editor as fixtures
from tests.test_images import photo


class ButtonBuilderTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def payload(self, buttons):
        form = CardForm.for_card(self.card)
        data = {name:form[name].value() or '' for name in form.fields}
        data.update(builder_mode='tiles', button_items=json.dumps(buttons))
        return data

    def test_builder_saves_order_titles_and_destinations_then_publishes_without_duplicates(self):
        buttons=[{'kind':'phone','label':'Позвонить','value':'89289091817'},
                 {'kind':'vk','label':'Мой VK','value':'vk.com/person'},
                 {'kind':'other_phone','label':'Офис','value':'+74951234567'},
                 {'kind':'link','label':'Наш сайт','value':'google.com'}]
        response=self.client.post(f'/app/cards/{self.card.pk}/edit', self.payload(buttons))
        self.assertEqual(response.status_code,303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['buttons'][0]['value'],'+79289091817')
        self.assertEqual(self.card.draft['buttons'][1]['label'],'Мой VK')
        publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response,'data-button-layout="tiles"')
        self.assertContains(response,'class="builder-contact-button"',count=4)
        self.assertContains(response,'href="https://vk.com/person"',count=1)
        self.assertContains(response,'href="tel:+74951234567"')
        self.assertIn('TEL;TYPE=VOICE:+74951234567',Client().get(f'/c/{self.card.public_id}/contact.vcf').content.decode())

    def test_existing_content_is_available_in_new_builder_without_modifying_snapshot(self):
        content={**self.card.draft,'phone':'+79289091817','email':'a@example.test','links':[{'label':'Сайт','url':'https://example.com'}],
                 'socials':{'telegram':'https://t.me/example'}}
        old=deepcopy(content); buttons=initial_buttons(content)
        self.assertEqual(len(buttons),4);self.assertEqual(content,old)
        save_card(self.user,self.card.pk,self.card.draft_version,content);self.card.refresh_from_db()
        response=self.client.get(f'/app/cards/{self.card.pk}/edit')
        self.assertContains(response,'card-builder.js');self.assertContains(response,'builder-options')
        self.card.refresh_from_db();self.assertNotIn('buttonLayout',self.card.draft)

    def test_background_control_and_customer_background_layer_are_removed(self):
        response=self.client.get(f'/app/cards/{self.card.pk}/edit')
        self.assertNotContains(response,'data-image-slot="background"')
        self.assertEqual({panel['target'] for panel in response.context['image_panels']},{'logo','header','avatar'})
        design=deepcopy(DEFAULT)
        save_card(self.user,self.card.pk,1,{**self.card.draft,'design':design})
        response=self.client.get(f'/app/cards/{self.card.pk}/edit')
        self.assertNotContains(response,'class="card-background"')
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertNotContains(Client().get(f'/c/{self.card.public_id}'),'class="card-background"')

    def test_save_and_close_saves_draft_and_returns_to_selected_card(self):
        data=self.payload([{'kind':'telegram','label':'Telegram','value':'t.me/person'}])
        data.update(name='Новое имя',save_and_close='yes')
        response=self.client.post(f'/app/cards/{self.card.pk}/edit',data)
        self.assertEqual(response.status_code,303)
        self.assertEqual(response['Location'],f'/app/cards?card={self.card.pk}')
        self.card.refresh_from_db();self.assertEqual(self.card.draft['name'],'Новое имя')
        self.assertEqual(self.card.draft['buttons'][0]['value'],'https://t.me/person')
        self.assertEqual(self.card.status,'draft')
        data.update(name='',draft_version=self.card.draft_version)
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/edit',data).status_code,422)

    def test_logo_is_independent_and_uses_owned_asset_routes(self):
        response=self.client.post('/app/assets',{'card_id':str(self.card.pk),'draft_version':1,'target':'logo','image':photo()})
        self.assertEqual(response.status_code,303)
        self.card.refresh_from_db();asset=self.card.draft['logoAssetId']
        self.assertNotIn('avatarAssetId',self.card.draft);self.assertNotIn('backgroundAssetId',self.card.draft)
        image_response=self.client.get(f'/app/cards/{self.card.pk}/assets/{asset}')
        self.assertEqual(image_response.status_code,200);b''.join(image_response.streaming_content)
        publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertContains(Client().get(f'/c/{self.card.public_id}'),'class="card-logo"')

    def test_public_photo_has_no_qr_toggle_but_owner_keeps_it(self):
        self.client.post('/app/assets',{'card_id':str(self.card.pk),'draft_version':1,'target':'avatar','image':photo()})
        self.card.refresh_from_db()
        for designed in (False,True):
            if designed:
                save_card(self.user,self.card.pk,self.card.draft_version,{**self.card.draft,'design':deepcopy(DEFAULT)})
                self.card.refresh_from_db()
            publish_card(self.user,self.card.pk,self.card.draft_version)
            public=Client().get(f'/c/{self.card.public_id}')
            self.assertContains(public,'avatar-photo-face')
            self.assertNotContains(public,'data-avatar-toggle')
            self.assertNotContains(public,'data-avatar-qr')
            self.assertNotContains(public,'Нажмите на фото, чтобы показать QR')
            self.assertContains(self.client.get(f'/app/cards/{self.card.pk}/edit'),'data-avatar-toggle')

    def test_invalid_buttons_are_rejected_and_local_file_can_wait_for_upload(self):
        for item in [{'kind':'bad','label':'X','value':'https://example.com'},
                     {'kind':'link','label':'X','value':'javascript:alert(1)'},
                     {'kind':'phone','label':'X','value':'bad'}]:
            with self.assertRaises(ValidationError):clean_buttons([item])
        self.assertEqual(clean_buttons([{'kind':'file','label':'Прайс','value':''}])[0]['value'],'')
        with self.assertRaises(ValidationError):clean_buttons([{'kind':'link','label':'X','value':'example.com'}]*31)

    def test_catalogue_design_uses_same_button_grid_and_omits_incomplete_file(self):
        data=self.payload([{'kind':'link','label':'Сайт','value':'example.com'}, {'kind':'youtube','label':'Мой канал','value':'youtube.com/@demo'}])
        save_card(self.user,self.card.pk,self.card.draft_version,{**self.card.draft,'design':deepcopy(DEFAULT)})
        self.card.refresh_from_db();data.update(template='design',draft_version=self.card.draft_version)
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/edit',data).status_code,303)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertContains(Client().get(f'/c/{self.card.public_id}'),'class="builder-contact-button"',count=2)
        data=self.payload([{'kind':'file','label':'Прайс','value':''}])
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/edit',data).status_code,303)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertNotContains(Client().get(f'/c/{self.card.public_id}'),'builder-contact-buttons')

    def test_uploaded_pdf_becomes_one_download_button(self):
        data=self.payload([{'kind':'file','label':'Мой прайс','value':''}])
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/edit',data).status_code,303)
        self.card.refresh_from_db()
        response=self.client.post(f'/app/cards/{self.card.pk}/content-media',{
            'operation':'pdf','draft_version':self.card.draft_version,
            'file':SimpleUploadedFile('price.pdf',b'%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF',content_type='application/pdf')})
        self.assertEqual(response.status_code,302)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response,'class="builder-contact-button"',count=1)
        self.assertNotContains(response,'class="card-pdf-button"')
        self.assertContains(response,self.card.draft['document']['assetId'])
