import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings, Client
from django.utils import timezone
from accounts.models import User
from workspaces.models import Workspace, Membership
from billing.models import Subscription
from cards.models import CardTemplate, TemplateIcon, TemplatePhoto, Asset
from cards.designs import DEFAULT, editor_design, validate_design
from cards.services import create_card, publish_card, save_card
from cards.asset_cleanup import cleanup_unused_assets
from tests.test_images import photo


def layout():
    design=editor_design(deepcopy(DEFAULT))
    design['hidden']=[]
    design['canvas']={'enabled':True,'height':1600}
    design['frames']={key:{'x':6,'y':index*170,'width':88,'unit':'%','height':0,'z':1,'corners':[0,4,8,12]} for index,key in enumerate(design['blocks'])}
    design['frames']['cover'].update(y=0,height=160)
    design['frames']['avatar'].update(x=35,y=80,width=30,height=108,z=4,corners=[100]*4)
    design['blockStyles']={'socials':{'align':'center','iconPosition':'left','buttonShape':'circle','buttonCorners':[1,2,3,4]}}
    design['socialMode']='radial'
    return design


class VisualEditorTests(TestCase):
    def setUp(self):
        directory=TemporaryDirectory();self.addCleanup(directory.cleanup)
        override=override_settings(PRIVATE_MEDIA_ROOT=Path(directory.name));override.enable();self.addCleanup(override.disable)
        self.user=User.objects.create_superuser('canvas@example.test','Canvas-Password-390!',email_verified_at=timezone.now())
        self.space=Workspace.objects.create(owner=self.user);Membership.objects.create(user=self.user,workspace=self.space)
        self.sub=Subscription.objects.create(workspace=self.space,status='active',paid_until=timezone.now()+timedelta(days=30))
        self.card=create_card(self.user);self.client.force_login(self.user)
        self.url=f'/app/cards/{self.card.pk}/design'

    def save(self,content=None,version=None):
        self.card.refresh_from_db()
        return self.client.post(self.url,{'draft_version':self.card.draft_version if version is None else version,'content':json.dumps(content or self.card.draft)},HTTP_ACCEPT='application/json')

    def upload(self,kind='gallery',image=None):
        self.card.refresh_from_db()
        return self.client.post(self.url+'/media',{'kind':kind,'draft_version':self.card.draft_version,'image':image or photo()})

    def test_visual_editor_and_layout_round_trip(self):
        response=self.client.get(self.url)
        self.assertContains(response,'data-visual-editor');self.assertContains(response,'data-resize="5"')
        content={**self.card.draft,'design':layout(),'socials':{'telegram':'https://t.me/test'}}
        self.assertEqual(self.save(content).status_code,200)
        self.card.refresh_from_db();self.assertEqual(self.card.draft['design'],layout())
        publish_card(self.user,self.card.pk,self.card.draft_version,publication_conditions='Не использовать для рекламы')
        response=self.client.get(f'/c/{self.card.public_id}')
        self.assertContains(response,'data-canvas-enabled="true"');self.assertContains(response,'top:calc(80px')
        self.assertContains(response,'data-social-mode="radial"');self.assertContains(response,'data-sun-toggle')
        self.assertContains(response,'Не использовать для рекламы')
        self.assertGreater(response.content.decode().index('Не использовать для рекламы'),response.content.decode().index('data-design-block="carousel"'))
        self.card.refresh_from_db();current=deepcopy(self.card.published_revision.content)
        content['design']['frames']['avatar']['y']=130;self.save(content)
        self.card.refresh_from_db();self.assertEqual(self.card.published_revision.content,current)
        self.assertEqual(self.save(content,version=1).status_code,409)

    def test_layout_is_bounded_and_does_not_accept_css(self):
        for mutate in [lambda d:d['frames']['cover'].update(x=95,width=80),lambda d:d['frames']['avatar'].update(y=-2),
                       lambda d:d['frames']['avatar'].update(x=float('nan')),lambda d:d['frames'].pop('identity'),
                       lambda d:d['frames']['bio'].update(html='<script/>'),lambda d:d['carousel'].update(photos=[str(self.card.pk)]*11),
                       lambda d:d['carousel'].update(interval=1),lambda d:d['frames']['cover'].update(corners=[1,2])]:
            design=layout();mutate(design)
            with self.subTest(design=design),self.assertRaises(ValidationError):validate_design(design)
        self.assertEqual(self.card.draft_version,1)

    def test_gallery_limit_render_and_publication_retains_images(self):
        content={**self.card.draft,'design':layout()};self.save(content)
        ids=[]
        for _ in range(10):
            response=self.upload();self.assertEqual(response.status_code,200);ids.append(response.json()['id'])
        self.assertEqual(self.upload().status_code,422)
        self.card.refresh_from_db();self.assertEqual(self.card.draft['galleryAssetIds'],ids)
        self.card.draft['design']['carousel'].update(visible=3,autoplay=True,interval=7)
        save_card(self.user,self.card.pk,self.card.draft_version,self.card.draft);self.card.refresh_from_db()
        publish_card(self.user,self.card.pk,self.card.draft_version)
        response=self.client.get(f'/c/{self.card.public_id}')
        self.assertContains(response,'data-visible="3"');self.assertContains(response,'data-interval="7"');self.assertContains(response,'data-autoplay="true"')
        for pk in ids:
            response=Client().get(f'/c/{self.card.public_id}/assets/{pk}')
            self.assertEqual(response.status_code,200);self.assertTrue(b''.join(response.streaming_content))
        current=deepcopy(self.card.draft);current['galleryAssetIds']=[]
        self.save(current);cleanup_unused_assets(self.space.pk)
        self.assertEqual(Asset.objects.filter(pk__in=ids).count(),10)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version);cleanup_unused_assets(self.space.pk)
        self.assertEqual(Asset.objects.filter(pk__in=ids).count(),0)

    def test_private_icons_and_foreign_resources(self):
        svg=SimpleUploadedFile('icon.svg',b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M0 0L24 24"/></svg>')
        response=self.upload('icon',svg);self.assertEqual(response.status_code,200);pk=response.json()['id']
        self.assertEqual(Client().get(f'/template-icons/{pk}.svg').status_code,404)
        self.assertEqual(self.client.get(f'/template-icons/{pk}.svg').status_code,200)
        content={**self.card.draft,'design':layout()};content['design']['icons']['telegram']=pk
        self.assertEqual(self.save(content).status_code,200);self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertEqual(Client().get(f'/template-icons/{pk}.svg').status_code,200)
        self.sub.paid_until=timezone.now()-timedelta(days=1);self.sub.save()
        self.assertEqual(Client().get(f'/template-icons/{pk}.svg').status_code,404)
        self.assertEqual(self.client.get(f'/template-icons/{pk}.svg')['Cache-Control'],'private, no-store')
        other=User.objects.create_user('other-canvas@example.test','Other-Password-298!')
        foreign=TemplateIcon.objects.create(name='Чужой',svg='<svg/>',owner=other)
        content['design']['icons']['telegram']=str(foreign.pk)
        self.assertEqual(self.save(content).status_code,422)
        self.assertEqual(self.upload('icon',SimpleUploadedFile('bad.svg',b'<svg><script/></svg>')).status_code,422)

    def test_ownership_and_csrf_on_all_mutations(self):
        other=User.objects.create_user('outsider@example.test','Password-982!')
        other_space=Workspace.objects.create(owner=other);Membership.objects.create(user=other,workspace=other_space)
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).status_code,404)
        self.assertEqual(self.upload().status_code,404)
        self.assertEqual(self.save().status_code,404)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url,{}).status_code,403)
        self.assertEqual(csrf.post(self.url+'/media',{}).status_code,403)

    def test_template_visual_save_and_direct_photo_upload(self):
        item=CardTemplate.objects.create(name='Холст',draft=deepcopy(DEFAULT))
        image=self.client.post('/control/template-media',{'kind':'header','image':photo()})
        self.assertEqual(image.status_code,200);pk=image.json()['id']
        self.assertEqual(Client().get(image.json()['url']).status_code,200)
        definition=layout();definition['images']={'header':pk};definition['carousel']['photos']=[pk]
        data={key:value for key,value in DEFAULT.items() if key not in ('blocks','icons')}
        data.update(version=1,name='Новый холст',description='',category='',position=0,block_order=','.join(DEFAULT['blocks']),visual_design=json.dumps(definition),operation='publish')
        response=self.client.post(f'/control/templates/{item.pk}',data)
        self.assertEqual(response.status_code,303);item.refresh_from_db();self.assertEqual(item.published,definition)
        self.assertEqual(self.client.post(f'/app/cards/{self.card.pk}/templates',{'template_id':item.pk,'draft_version':1}).status_code,303)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertContains(self.client.get(f'/c/{self.card.public_id}'),image.json()['url'])

    def test_template_ajax_save_keeps_errors_on_the_canvas_and_updates_version(self):
        item=CardTemplate.objects.create(name='Холст',draft=deepcopy(DEFAULT))
        definition=layout()
        data={key:value for key,value in DEFAULT.items() if key not in ('blocks','icons')}
        data.update(version=1,name='Холст',description='',category='',position=0,block_order=','.join(DEFAULT['blocks']),visual_design=json.dumps(definition))
        response=self.client.post(f'/control/templates/{item.pk}',data,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['version'],2)
        self.assertEqual(self.client.post(f'/control/templates/{item.pk}',data,HTTP_ACCEPT='application/json').status_code,409)
        data['version']=2;definition['text']='#ffffff';data['visual_design']=json.dumps(definition)
        response=self.client.post(f'/control/templates/{item.pk}',data,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,422);self.assertIn('error',response.json())
        item.refresh_from_db();self.assertEqual(item.version,2)

    def test_visual_editor_preserves_template_colour_permissions_and_current_accent(self):
        definition=layout();definition.update(sourceId=str(self.card.pk),sourceVersion=1,sourceName='Шаблон',allowAccent=False,allowFont=False)
        content={**self.card.draft,'design':definition};self.assertEqual(self.save(content).status_code,200)
        content['accent']='#000000';self.assertEqual(self.save(content).status_code,422)
        self.card.refresh_from_db();content=deepcopy(self.card.draft);content['design']['font']='serif'
        self.assertEqual(self.save(content).status_code,422)
        self.card.draft['design']['allowAccent']=True;self.card.draft['accent']='#111111';self.card.save()
        response=self.client.get(self.url)
        self.assertEqual(response.context['editor_data']['design']['accent'],'#111111')

    def test_publishing_a_template_copies_own_private_icons_into_shared_resources(self):
        private=TemplateIcon.objects.create(name='Личный значок',svg='<svg xmlns="http://www.w3.org/2000/svg"/>',owner=self.user)
        item=CardTemplate.objects.create(name='Шаблон',draft=deepcopy(DEFAULT))
        definition=layout();definition['icons']['telegram']=str(private.pk)
        payload={key:value for key,value in DEFAULT.items() if key not in ('blocks','icons')}
        payload.update(version=1,name='Шаблон',description='',category='',position=0,block_order=','.join(DEFAULT['blocks']),visual_design=json.dumps(definition),operation='publish')
        response=self.client.post(f'/control/templates/{item.pk}',payload,HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,200)
        item.refresh_from_db();shared=item.published['icons']['telegram']
        self.assertNotEqual(shared,str(private.pk));self.assertIsNone(TemplateIcon.objects.get(pk=shared).owner_id)
        self.assertEqual(Client().get(f'/template-icons/{shared}.svg').status_code,200)
