from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from cards.button_builder import clean_buttons
from cards.validation import validate_content
from cards.vcard import render_vcard


class ButtonInputTests(SimpleTestCase):
    def clean(self,kind,value,**extra):
        return clean_buttons([{'kind':kind,'label':'Контакт','value':value,**extra}])[0]

    def test_phone_normalizes_mask_and_extension_is_separate(self):
        item=self.clean('phone','+7 (928) 909-18-17',extension='123')
        self.assertEqual(item['value'],'+79289091817');self.assertEqual(item['extension'],'123')
        content={'schemaVersion':1,'template':'classic','name':'Имя','accent':'#2457DB','links':[],
                 'phone':item['value'],'buttons':[item],'buttonLayout':'tiles'}
        validate_content(content)
        vcard=render_vcard(content,'https://visiooo.ru/c/example').decode().replace('\r\n ','')
        self.assertIn('добавочный 123',vcard)
        for number in ['+7 (928) 909','+792890918171','abc89289091817']:
            with self.assertRaises(ValidationError):self.clean('phone',number)
        for extension in ['12x','1;ext=2','123456789']:
            with self.assertRaises(ValidationError):self.clean('phone','89289091817',extension=extension)
        with self.assertRaises(ValidationError):self.clean('telegram','person',extension='123')

    def test_whatsapp_numbers_and_existing_links_normalize_to_wa_me(self):
        for value in ['89289091817','+7 (928) 909-18-17','https://wa.me/79289091817',
                      'https://api.whatsapp.com/send?phone=79289091817']:
            self.assertEqual(self.clean('whatsapp',value)['value'],'https://wa.me/79289091817')
        with self.assertRaises(ValidationError):self.clean('whatsapp','https://evil.test/79289091817')

    def test_usernames_are_expanded_and_existing_profile_links_work(self):
        cases=[('telegram','@person','https://t.me/person'),('telegram','person.t.me','https://t.me/person'),
               ('instagram','person.name','https://www.instagram.com/person.name'),
               ('vk','id123456','https://vk.com/id123456'),('youtube','@channel','https://www.youtube.com/@channel'),
               ('threads','person','https://www.threads.net/@person')]
        for kind,value,expected in cases:self.assertEqual(self.clean(kind,value)['value'],expected)
        for kind,value in [('max','max.ru/u/person'),('dzen','dzen.ru/person'),('ok','ok.ru/profile/123'),
                           ('avito','avito.ru/user/123'),('viber','invite.viber.com/example')]:
            self.assertTrue(self.clean(kind,value)['value'].startswith('https://'))

    def test_wrong_network_credentials_and_extra_characters_are_rejected(self):
        for kind,value in [('telegram','hello world'),('vk','https://vk.com.evil.test/name'),
                           ('instagram','https://evil.test/name'),('telegram','https://t.me'),
                           ('link','https://user:password@example.com'),('link','example.com/white space'),
                           ('link','javascript:alert(1)')]:
            with self.assertRaises(ValidationError,msg=f'{kind}: {value}'):self.clean(kind,value)
