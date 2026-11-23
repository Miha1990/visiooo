from copy import deepcopy
from django.test import TestCase, Client
from cards.designs import DEFAULT
from cards.services import save_card, publish_card
from tests import test_visual_editor as fixtures


class ContactSavingTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def publish_content(self, designed=False):
        content={**self.card.draft,'name':'Анна Иванова','title':'Дизайнер','company':'Студия',
                 'bio':'Описание работы','phone':'+79289091817','email':'anna@example.test',
                 'buttonLayout':'tiles','buttons':[{'kind':'phone','label':'Позвонить','value':'+79289091817'}]}
        if designed:
            content['design']=deepcopy(DEFAULT)
            blocks=content['design']['blocks'];blocks.remove('save');blocks.append('save')
        save_card(self.user,self.card.pk,self.card.draft_version,content)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)

    def test_save_button_follows_profile_and_precedes_contact_blocks_in_both_layouts(self):
        for designed in (False,True):
            self.publish_content(designed)
            html=Client().get(f'/c/{self.card.public_id}').content.decode()
            self.assertLess(html.index('data-preview="bio"'),html.index('class="contact-save-group"'))
            self.assertLess(html.index('class="contact-save-group"'),html.index('class="contact-actions'))
            self.assertIn('data-save-contact',html)
            self.assertNotIn('download data-save-contact',html)

    def test_vcard_can_open_natively_and_has_explicit_download_fallback(self):
        self.publish_content()
        url=f'/c/{self.card.public_id}/contact.vcf'
        for ua in ['Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)',
                   'Mozilla/5.0 (Linux; Android 15)', 'Mozilla/5.0 (Windows NT 10.0)']:
            response=Client().get(url,HTTP_USER_AGENT=ua)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response['Content-Type'],'text/vcard; charset=utf-8')
            self.assertEqual(response['Content-Disposition'],'inline; filename="contact.vcf"')
            self.assertTrue(response.content.startswith(b'BEGIN:VCARD\r\nVERSION:3.0\r\n'))
            self.assertTrue(response.content.endswith(b'END:VCARD\r\n'))
            self.assertIn('FN:Анна Иванова',response.content.decode())
            self.assertIn(b'TEL;TYPE=CELL:+79289091817',response.content)
            self.assertNotIn(self.user.email.encode(),response.content)
        download=Client().get(url+'?download=1')
        self.assertEqual(download['Content-Disposition'],'attachment; filename="contact.vcf"')
        self.assertEqual(download.content,response.content)

    def test_vcard_keeps_secondary_contacts_and_address_without_duplicate_numbers(self):
        from cards.vcard import render_vcard
        content={'name':'Имя','phone':'+79289091817','email':'a@example.test',
                 'map':{'address':'Ростов-на-Дону, Зорге 27'},'buttons':[
                     {'kind':'phone','value':'+79289091817','label':'Мобильный'},
                     {'kind':'other_phone','value':'+74951234567','label':'Офис'},
                     {'kind':'other_phone','value':'+74951234567','label':'Офис'},
                     {'kind':'email','value':'second@example.test','label':'Почта'}]}
        vcard=render_vcard(content,'https://visiooo.ru/c/example').decode().replace('\r\n ','')
        self.assertEqual(vcard.count('TEL;TYPE='),2)
        self.assertIn('EMAIL;TYPE=INTERNET:second@example.test',vcard)
        self.assertIn('ADR;TYPE=WORK:;;Ростов-на-Дону\\, Зорге 27;;;;',vcard)
