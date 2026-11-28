import json
from copy import deepcopy
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase
from cards.blocks import video_embed, video_player_url, map_embed
from cards.models import CardBlockSettings, Asset
from cards.services import publish_card, save_card
from cards.asset_cleanup import cleanup_unused_assets
from tests import test_visual_editor as fixtures
layout = fixtures.layout


class EmbedParsingTests(SimpleTestCase):
    def test_vk_clip_share_links_and_matching_player(self):
        for domain in ('vkvideo.ru', 'vk.com', 'vk.ru', 'm.vk.com', 'm.vk.ru'):
            with self.subTest(domain=domain):
                clip = f'https://{domain}/clip-243793209_456239017?sh=4'
                expected_domain = 'vk.ru' if domain in ('vk.ru', 'm.vk.ru') else 'vk.com'
                self.assertEqual(video_player_url(clip),
                                 f'https://{expected_domain}/video_ext.php?oid=-243793209&id=456239017')
                player = 'https://vk.ru/video_ext.php?oid=-243793209&id=456239017&hash=18d01ce3990d425a'
                self.assertEqual(video_player_url(clip, player), player)
                with self.assertRaises(ValidationError):
                    video_player_url(clip, player.replace('id=456239017', 'id=1'))

    def test_vk_ru_player_and_video_links(self):
        player = 'https://vk.ru/video_ext.php?oid=-243793209&id=456239017&hash=18d01ce3990d425a&hd=4&autoplay=1'
        expected = 'https://vk.ru/video_ext.php?oid=-243793209&id=456239017&hash=18d01ce3990d425a'
        self.assertEqual(video_player_url(player), expected)
        self.assertEqual(video_player_url('https://vkvideo.ru/video-243793209_456239017', player), expected)
        self.assertEqual(video_player_url('https://vk.ru/video-243793209_456239017'),
                         'https://vk.ru/video_ext.php?oid=-243793209&id=456239017')
        for original, override in [('https://vk.ru/video-243793209_1', player),
                                   ('https://vk.ru/video-243793209_456239017', player.replace('vk.ru', 'vk.ru.evil.test'))]:
            with self.subTest(original=original), self.assertRaises(ValidationError):
                video_player_url(original, override)

    def test_supported_providers(self):
        self.assertEqual(video_embed('https://youtu.be/dQw4w9WgXcQ'), 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')
        self.assertEqual(video_embed('https://youtube.com/shorts/dQw4w9WgXcQ'), 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')
        self.assertEqual(video_embed('https://rutube.ru/video/'+'a'*32+'/'), 'https://rutube.ru/play/embed/'+'a'*32)
        self.assertIn('p=secret',video_embed('https://rutube.ru/video/private/'+'b'*32+'/?p=secret'))
        self.assertEqual(video_embed('https://vkvideo.ru/video-12_345','https://vk.com/video_ext.php?oid=-12&id=345&hash=abc'), 'https://vk.com/video_ext.php?oid=-12&id=345&hash=abc')

    def test_rejects_foreign_urls_and_mismatching_players(self):
        for url,extra in [('javascript:alert(1)',''),('https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ',''),
                          ('https://user@youtube.com/watch?v=dQw4w9WgXcQ',''),('https://127.0.0.1/video',''),
                          ('https://vk.com/video-12_345','https://vk.com/video_ext.php?oid=-13&id=345'),
                          ('https://vk.com/video-12_345','https://evil.test/video_ext.php?oid=-12&id=345')]:
            with self.subTest(url=url),self.assertRaises(ValidationError): video_embed(url,extra)

    def test_address_encoded_and_coordinates_pin(self):
        self.assertIn('text=',map_embed({'address':'Ростов-на-Дону, Зорге 27'}))
        self.assertIn('pt=39.7%2C47.2%2Cpm2rdm',map_embed({'address':'Адрес','latitude':47.2,'longitude':39.7}))


class CardBlockTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp
    save = fixtures.VisualEditorTests.save
    upload = fixtures.VisualEditorTests.upload
    def test_custom_gallery_limit_and_lowering_preserves_existing_content(self):
        CardBlockSettings.objects.create(carousel_limit=12)
        response=self.client.get(self.url)
        self.assertContains(response,'"carouselLimit": 12')
        self.assertEqual(self.save({**self.card.draft,'design':layout()}).status_code,200)
        for _ in range(12):self.assertEqual(self.upload().status_code,200)
        self.assertEqual(self.upload().status_code,422)
        CardBlockSettings.objects.filter(pk=1).update(carousel_limit=5)
        self.card.refresh_from_db()
        self.assertEqual(self.save().status_code,200)
        self.assertEqual(self.upload().status_code,422)

    def test_pdf_private_until_published_and_old_publication_survives_replacement(self):
        self.assertEqual(self.save({**self.card.draft,'design':layout()}).status_code,200)
        response=self.upload('pdf',SimpleUploadedFile('price.pdf',b'%PDF-1.4\nfirst\n%%EOF\n'))
        self.assertEqual(response.status_code,200);old=response.json()['id']
        self.assertEqual(Client().get(response.json()['url']).status_code,302)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        url=f'/c/{self.card.public_id}/assets/{old}'
        response=Client().get(url)
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertIn('attachment',response['Content-Disposition'])
        self.assertIn(b'first',b''.join(response.streaming_content))
        response=self.upload('pdf',SimpleUploadedFile('new.pdf',b'%PDF-1.4\nsecond\n%%EOF\n'))
        self.assertEqual(response.status_code,200);new=response.json()['id']
        cleanup_unused_assets(self.space.pk)
        response=Client().get(url);self.assertIn(b'first',b''.join(response.streaming_content))
        self.assertEqual(Client().get(f'/c/{self.card.public_id}/assets/{new}').status_code,404)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        cleanup_unused_assets(self.space.pk)
        self.assertFalse(Asset.objects.filter(pk=old).exists())
        self.assertEqual(Client().get(url).status_code,404)

    def test_pdf_validation_stale_version_and_no_image_confusion(self):
        self.assertEqual(self.upload('pdf',SimpleUploadedFile('x.pdf',b'<script>bad</script>')).status_code,422)
        response=self.upload('pdf',SimpleUploadedFile('x.pdf',b'%PDF-1.4\n%%EOF'))
        self.assertEqual(response.status_code,200)
        self.card.refresh_from_db();content=deepcopy(self.card.draft)
        content['avatarAssetId']=response.json()['id']
        self.assertEqual(self.save(content).status_code,422)
        response=self.client.post(self.url+'/media',{'kind':'pdf','draft_version':1,'image':SimpleUploadedFile('x.pdf',b'%PDF-1.4\n%%EOF')})
        self.assertEqual(response.status_code,409)

    def test_video_map_render_ready_without_intermediate_buttons(self):
        content={**self.card.draft,'design':layout(),'video':{'url':'https://youtu.be/dQw4w9WgXcQ','title':'Наше видео'},
                 'map':{'address':'Ростов-на-Дону, ул. Зорге, 27','latitude':47.2,'longitude':39.7}}
        self.assertEqual(self.save(content).status_code,200)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        response=Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response,'Наше видео');self.assertContains(response,'data-embed-url="https://www.youtube-nocookie.com/embed/')
        self.assertNotContains(response,'data-load-embed');self.assertContains(response,'<iframe',count=2)
        self.assertContains(response,'src="https://www.youtube-nocookie.com/embed/')
        self.assertContains(response,'src="https://yandex.ru/map-widget/v1/')
        content['map']['latitude']=float('nan')
        self.assertEqual(self.save(content).status_code,422)

    def test_hidden_video_and_map_do_not_create_iframes(self):
        design = layout();design['hidden'] = ['video', 'map']
        content = {**self.card.draft, 'design':design, 'video':{'url':'https://youtu.be/dQw4w9WgXcQ'},
                   'map':{'address':'Ростов-на-Дону'}}
        self.assertEqual(self.save(content).status_code,200)
        self.card.refresh_from_db();publish_card(self.user,self.card.pk,self.card.draft_version)
        self.assertNotContains(Client().get(f'/c/{self.card.public_id}'), '<iframe')
