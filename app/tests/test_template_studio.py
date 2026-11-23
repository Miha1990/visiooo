from copy import deepcopy
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from accounts.models import User
from workspaces.models import Workspace, Membership
from billing.models import Subscription
from cards.models import CardTemplate, TemplateIcon
from cards.designs import DEFAULT, validate_design
from cards.forms import CardForm
from cards.services import create_card, publish_card
from cards.template_icons import sanitize_svg


class StudioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('studio@example.test', 'Password-579!')
        self.user.email_verified_at = timezone.now()
        self.user.save()
        self.workspace = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.workspace)
        Subscription.objects.create(workspace=self.workspace, status='active', paid_until=timezone.now()+timedelta(days=30))
        self.card = create_card(self.user)
        self.item = CardTemplate.objects.create(name='Первый', draft=deepcopy(DEFAULT))
        self.client.force_login(self.user)

    def data(self, **changes):
        data = deepcopy(DEFAULT)
        data.pop('blocks');data.pop('icons')
        data.update(name='Шаблон', description='Описание', category='Дизайнеры', position=1,
                    version=self.item.version, block_order=','.join(reversed(DEFAULT['blocks'])))
        data.update(changes)
        return data

    def test_studio_pages_and_permission(self):
        for path in ['/control/templates',f'/control/templates/{self.item.pk}','/control/icons',f'/app/cards/{self.card.pk}/templates']:
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.user.is_superuser=False;self.user.is_staff=False;self.user.save()
        self.assertEqual(self.client.get('/control/templates').status_code,302)
        self.user.is_staff=True;self.user.save()
        self.assertEqual(self.client.get('/control/templates').status_code,403)

    def test_publish_edit_archive_and_customer_snapshot(self):
        url=f'/control/templates/{self.item.pk}'
        self.assertEqual(self.client.post(url,self.data(operation='publish')).status_code,303)
        self.item.refresh_from_db()
        self.assertEqual(self.item.published_version,1)
        self.assertEqual(self.item.published['blocks'],list(reversed(DEFAULT['blocks'])))
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/templates',{'template_id':self.item.pk,'draft_version':1}).status_code,303)
        self.card.refresh_from_db()
        chosen=deepcopy(self.card.draft)
        publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertContains(self.client.get(f'/c/{self.card.public_id}'),'designed-card')
        self.assertContains(self.client.get(f'/app/cards/{self.card.pk}/edit'),'Из каталога: Шаблон')
        self.assertEqual(self.client.post(url,self.data(caption='Новая надпись')).status_code,303)
        self.item.refresh_from_db()
        self.assertEqual(self.item.published['caption'],DEFAULT['caption'])
        self.assertEqual(self.client.post(url,self.data(operation='publish',caption='Новая надпись')).status_code,303)
        self.item.refresh_from_db();self.card.refresh_from_db()
        self.assertEqual(self.card.draft,chosen)
        self.assertEqual(self.card.published_revision.content,chosen)
        self.assertEqual(self.client.post(f'{url}/archive',{'version':self.item.version}).status_code,303)
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/templates',{'template_id':self.item.pk,'draft_version':2}).status_code,404)
        # The stored caption is retained, but an empty header is omitted publicly.
        self.assertNotContains(self.client.get(f'/c/{self.card.public_id}'),DEFAULT['caption'])

    def test_stale_and_invalid_design_not_saved(self):
        url=f'/control/templates/{self.item.pk}'
        self.assertEqual(self.client.post(url,self.data(version=999)).status_code,409)
        self.assertEqual(self.client.post(url,self.data(block_order='identity,save')).status_code,422)
        self.assertEqual(self.client.post(url,self.data(text='#ffffff')).status_code,422)
        self.item.refresh_from_db();self.assertEqual(self.item.version,1)
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/templates',{'template_id':'bad'}).status_code,404)

    def test_save_own_style_excludes_personal_data(self):
        self.card.draft.update(name='Секретное имя', email='private@example.test', accent='#174a72')
        self.card.save()
        response=self.client.post(f'/control/templates/from-card/{self.card.pk}')
        self.assertEqual(response.status_code,303)
        item=CardTemplate.objects.exclude(pk=self.item.pk).get()
        self.assertEqual(item.draft['accent'],'#174a72')
        self.assertNotIn('Секретное',str(item.draft));self.assertNotIn('private@',str(item.draft))
        other=User.objects.create_user('other@example.test','Password-579!')
        other_ws=Workspace.objects.create(owner=other);Membership.objects.create(user=other,workspace=other_ws)
        other_card=create_card(other)
        self.assertEqual(self.client.post(f'/control/templates/from-card/{other_card.pk}').status_code,404)

    def test_form_preserves_snapshot_and_locks_preferences(self):
        self.card.draft['design']={**deepcopy(DEFAULT),'allowAccent':False,'allowFont':True,'sourceName':'Свой'}
        self.card.save()
        payload={'name':'Новое имя','template':'design','accent':'#000000','draft_version':1,'links':'','design_font':'serif'}
        form=CardForm.for_card(self.card,payload)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.content['design']['font'],'serif')
        self.assertEqual(form.content['accent'],self.card.draft['accent'])
        payload.update(template='profile')
        form=CardForm.for_card(self.card,payload)
        self.assertTrue(form.is_valid(),form.errors);self.assertNotIn('design',form.content)

    def test_svg_upload_and_delivery(self):
        svg=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0L24 24" stroke="#000"/></svg>'
        self.assertEqual(self.client.post('/control/icons',{'name':'Значок','image':SimpleUploadedFile('icon.svg',svg)}).status_code,303)
        item=TemplateIcon.objects.get()
        response=self.client.get(f'/template-icons/{item.pk}.svg')
        self.assertEqual(response['Content-Type'],'image/svg+xml')
        self.assertIn('sandbox',response['Content-Security-Policy'])
        data=self.data(operation='publish',icon_phone=str(item.pk))
        self.assertEqual(self.client.post(f'/control/templates/{self.item.pk}',data).status_code,303)
        self.assertContains(self.client.get(f'/control/templates/{self.item.pk}'),f'/template-icons/{item.pk}.svg')
        for malicious in [b'<svg><script/></svg>',b'<svg onload="alert(1)"/>',b'<svg><image href="https://evil.test"/></svg>',b'<!DOCTYPE svg><svg/>',b'<svg><path fill="url(https://evil.test)"/></svg>',b'<svg><foreignObject/></svg>']:
            with self.subTest(svg=malicious),self.assertRaises(ValidationError):sanitize_svg(malicious)

    def test_bounded_design(self):
        for changes in [{'hidden':['identity']},{'font':'url(evil)'},{'gap':1000},{'blocks':['identity']},{'text':'red;position:fixed'},
                        {'blockStyles':{'unknown':{}}},
                        {'blockStyles':{'identity':{'align':'center;position:fixed','iconPosition':'left','iconSize':24}}},
                        {'blockStyles':{'contacts':{'align':'left','iconPosition':'none','iconSize':999}}}]:
            with self.subTest(changes=changes),self.assertRaises(ValidationError):validate_design({**deepcopy(DEFAULT),**changes})

    def test_independent_block_settings_persist_and_render(self):
        icon=TemplateIcon.objects.create(name='Мой значок',svg='<svg xmlns="http://www.w3.org/2000/svg"/>')
        data=self.data(operation='publish',block_identity_align='center',block_contacts_align='left',
            block_contacts_iconPosition='none',block_socials_align='right',block_socials_iconPosition='top',
            block_socials_iconSize=32,block_identity_icon=str(icon.pk))
        self.assertEqual(self.client.post(f'/control/templates/{self.item.pk}',data).status_code,303)
        self.item.refresh_from_db()
        self.assertEqual(self.item.published['blockStyles']['identity']['align'],'center')
        self.assertEqual(self.item.published['blockStyles']['contacts']['align'],'left')
        self.assertEqual(self.item.published['blockStyles']['socials']['iconSize'],32)
        self.client.post(f'/app/cards/{self.card.pk}/templates',{'template_id':self.item.pk,'draft_version':1})
        self.card.refresh_from_db()
        self.card.draft['phone']='+79991234567';self.card.save()
        publish_card(self.user,self.card.pk,self.card.draft_version)
        response=self.client.get(f'/c/{self.card.public_id}')
        self.assertContains(response,'data-design-block="identity" data-block-align="center"')
        self.assertContains(response,'data-design-block="contacts" data-block-align="left" data-block-icons="none"')
        self.assertContains(response,f'src="/template-icons/{icon.pk}.svg"')

    def test_old_snapshots_keep_working_without_block_overrides(self):
        self.card.draft['design']=deepcopy(DEFAULT);self.card.save()
        publish_card(self.user,self.card.pk,1)
        self.assertContains(self.client.get(f'/c/{self.card.public_id}'),'data-block-align="inherit"')
        self.assertNotIn('blockStyles',self.card.draft['design'])

    def test_named_link_buttons_save_and_never_show_the_url_as_text(self):
        from html.parser import HTMLParser
        class VisibleText(HTMLParser):
            def __init__(self):super().__init__();self.text=[]
            def handle_data(self,data):self.text.append(data)
        url='https://www.instagram.com/test_profile/'
        for template in ['classic','minimal','profile','design']:
            self.card.refresh_from_db()
            if template=='design':
                self.card.draft['design']=deepcopy(DEFAULT);self.card.save()
            response=self.client.post(f'/app/cards/{self.card.pk}/edit',{'name':'Тест','template':template,'accent':'#2457DB',
                'draft_version':self.card.draft_version,'links_label':['Инстаграм',''], 'links_url':[url,''],
                'social_instagram':'https://www.instagram.com/another_profile/'})
            self.assertEqual(response.status_code,303)
            self.card.refresh_from_db()
            self.assertEqual(self.card.draft['links'],[{'label':'Инстаграм','url':url}])
            publish_card(self.user,self.card.pk,self.card.draft_version)
            response=self.client.get(f'/c/{self.card.public_id}')
            self.assertContains(response,f'href="{url}"')
            parser=VisibleText();parser.feed(response.content.decode())
            visible=' '.join(parser.text)
            self.assertIn('Инстаграм',visible);self.assertNotIn(url,visible)
            self.assertNotIn('https://www.instagram.com/another_profile/',visible)
        response=self.client.get(f'/app/cards/{self.card.pk}/edit')
        self.assertContains(response,'Название кнопки 1')
        self.assertContains(response,f'value="{url}"')

    def test_named_link_buttons_validate_missing_label_and_unsafe_address(self):
        for label,url in [('', 'https://example.test'),('Кнопка','javascript:alert(1)')]:
            response=self.client.post(f'/app/cards/{self.card.pk}/edit',{'name':'Тест','template':'classic','accent':'#2457DB',
                'draft_version':1,'links_label':[label],'links_url':[url]})
            self.assertEqual(response.status_code,422)
        self.card.refresh_from_db();self.assertEqual(self.card.draft_version,1)

    @override_settings(ROOT_URLCONF='domains.public_urls')
    def test_public_icon_available_on_custom_domain_urlconf(self):
        item=TemplateIcon.objects.create(name='Линия',svg=sanitize_svg(b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0L24 24"/></svg>'))
        self.assertEqual(self.client.get(f'/template-icons/{item.pk}.svg').status_code,200)

    def test_apply_preserves_all_three_images_and_private_contacts(self):
        from cards.models import Asset
        for slot in ['avatarAssetId','headerAssetId','backgroundAssetId']:
            asset=Asset.objects.create(workspace=self.workspace,object_key=f'{slot}.webp',width=80,height=80,bytes=100)
            self.card.draft[slot]=str(asset.pk)
        self.card.draft.update(phone='+79991234567',email='private@example.test',links=[{'label':'Мой сайт','url':'https://example.test'}])
        self.card.save()
        previous=deepcopy(self.card.draft)
        self.item.status='published';self.item.published=deepcopy(DEFAULT);self.item.published_version=1;self.item.save()
        response=self.client.post(f'/app/cards/{self.card.pk}/templates',{'template_id':self.item.pk,'draft_version':1})
        self.assertEqual(response.status_code,303)
        self.card.refresh_from_db()
        for key,value in previous.items():self.assertEqual(self.card.draft[key],value)
