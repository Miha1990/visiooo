import json

from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase

from cards.blocks import video_embed, video_player_url
from cards.forms import CardForm
from cards.services import publish_card, save_card
from cards.validation import validate_content
from tests import test_visual_editor as fixtures


class VideoProviderTests(SimpleTestCase):
    def test_new_embeds_and_private_vimeo_links(self):
        cases = [
            ('https://vimeo.com/123456789', '', 'https://player.vimeo.com/video/123456789'),
            ('https://vimeo.com/123456789/abc123', '', 'https://player.vimeo.com/video/123456789?h=abc123'),
            ('https://player.vimeo.com/video/123456789?h=abc123', '', 'https://player.vimeo.com/video/123456789?h=abc123'),
            ('https://ok.ru/video/123456789', '', 'https://ok.ru/videoembed/123456789'),
            ('https://www.tiktok.com/@person/video/6718335390845095173', '', 'https://www.tiktok.com/player/v1/6718335390845095173'),
            ('https://dailymotion.com/video/x84sh87', 'https://geo.dailymotion.com/player/x8lr5.html?video=x84sh87', 'https://geo.dailymotion.com/player/x8lr5.html?video=x84sh87'),
            ('https://rutube.ru/shorts/' + 'a'*32, '', 'https://rutube.ru/play/embed/' + 'a'*32),
        ]
        for url, override, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(video_embed(url, override), expected)

    def test_other_services_are_links_without_arbitrary_iframes(self):
        for url in ('https://dzen.ru/video/watch/abc', 'https://www.instagram.com/reel/abc/',
                    'https://www.facebook.com/watch/?v=123', 'https://www.twitch.tv/videos/123',
                    'https://dailymotion.com/video/x84sh87', 'https://vm.tiktok.com/abc/',
                    'https://plvideo.ru/watch?v=abc', 'https://kinescope.io/abc'):
            with self.subTest(url=url):
                self.assertEqual(video_player_url(url), '')
        for url, override in [('javascript:alert(1)', ''), ('https://127.0.0.1/video', ''),
                ('https://user@example.com/video', ''), ('https://example.local/video', ''),
                ('https://vimeo.com/123', 'https://evil.test/player'),
                ('https://dailymotion.com/video/x84sh87', 'https://geo.dailymotion.com/player/x8lr5.html?video=other')]:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                video_player_url(url, override)


class VideoCarouselTests(TestCase):
    setUp = fixtures.VisualEditorTests.setUp

    def payload(self, extra, **changes):
        form = CardForm.for_card(self.card)
        data = {name: form[name].value() or '' for name in form.fields}
        data.update({'video_url':'https://youtu.be/dQw4w9WgXcQ', 'video_title':'Первый ролик',
                    'video_items':json.dumps(extra), **changes})
        return data

    def test_builder_keeps_player_size_and_multiple_videos_after_reopening_and_publishing(self):
        extra = [{'url': 'https://vkvideo.ru/clip-243793209_456239017?sh=4', 'title': 'Вертикальный клип',
                  'embedUrl': 'https://vk.ru/video_ext.php?oid=-243793209&id=456239017&hash=18d01ce3990d425a'},
                 {'url': 'https://vimeo.com/123456789', 'title': 'Третий ролик', 'embedUrl': ''}]
        layout = {'blocks': {'video': {'width': 75, 'height': 240}}}
        url = f'/app/cards/{self.card.pk}/edit'
        response = self.client.post(url, self.payload(extra, builder_mode='tiles', button_items='[]', layout_data=json.dumps(layout)))
        self.assertEqual(response.status_code, 303)
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['layout'], layout)
        restored = CardForm.for_card(self.card)
        self.assertEqual(json.loads(restored['layout_data'].value()), layout)
        self.assertEqual(json.loads(restored['video_items'].value()), extra)
        # Saving again from the restored editor retains every slide and its player URL.
        data = {name: restored[name].value() or '' for name in restored.fields}
        data['builder_mode'] = 'tiles'
        self.assertEqual(self.client.post(url, data).status_code, 303)
        self.card.refresh_from_db()
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.card.refresh_from_db()
        response = Client().get(f'/c/{self.card.public_id}')
        self.assertContains(response, 'class="video-slide"', count=3)
        self.assertContains(response, 'data-video-aspect="9/16"', count=1)
        self.assertEqual(self.card.published_revision.content['layout'], layout)
        self.assertEqual(self.card.published_revision.content['videos'][1:], extra)

    def test_save_preview_publish_remove_and_keep_previous_publication(self):
        extra = [{'url':'vimeo.com/123456789', 'title':'Второй ролик'},
                 {'url':'https://dzen.ru/video/watch/abc', 'title':'Третий ролик'}]
        url = f'/app/cards/{self.card.pk}/edit'
        self.assertEqual(self.client.post(url, self.payload(extra)).status_code, 303)
        self.card.refresh_from_db()
        self.assertEqual(len(self.card.draft['videos']), 3)
        self.assertEqual(self.card.draft['videos'][1]['url'], 'https://vimeo.com/123456789')
        response = self.client.get(url)
        self.assertContains(response, 'name="video_items"', count=1)
        self.assertContains(response, 'card-videos.js')
        publish_card(self.user, self.card.pk, self.card.draft_version)
        public_url = f'/c/{self.card.public_id}'
        response = Client().get(public_url)
        self.assertContains(response, 'class="video-slide"', count=3)
        self.assertContains(response, '<iframe', count=1)
        self.assertContains(response, 'Третий ролик')
        self.assertNotContains(response, 'data-video-next')
        self.assertNotContains(response, 'data-video-prev')
        self.assertNotContains(response, 'data-video-status')
        self.assertContains(response, 'data-video-multiple="true"')
        self.assertEqual(self.client.post(url, self.payload([])).status_code, 303)
        self.card.refresh_from_db()
        self.assertNotIn('videos', self.card.draft)
        self.assertContains(Client().get(public_url), 'Третий ролик')
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assertNotContains(Client().get(public_url), 'Третий ролик')
        self.assertEqual(self.client.post(url, self.payload([], video_url='', video_title='')).status_code, 303)
        self.card.refresh_from_db()
        self.assertNotIn('video', self.card.draft)

    def test_limit_malformed_data_and_unsafe_links_are_rejected_without_saving(self):
        for extra in ([{'url':'https://vimeo.com/123'}]*20, {'url':'https://vimeo.com/123'},
                      [{'url':''}], [{'url':'javascript:alert(1)'}]):
            with self.subTest(extra=extra):
                response = self.client.post(f'/app/cards/{self.card.pk}/edit', self.payload(extra))
                self.assertEqual(response.status_code, 422)
                self.card.refresh_from_db()
                self.assertEqual(self.card.draft_version, 1)

    def test_collection_supported_in_every_template_and_direct_json_is_validated(self):
        videos = [{'url':'https://vimeo.com/123456789', 'title':'Vimeo'},
                  {'url':'https://ok.ru/video/123456789', 'title':'ОК'}]
        for template in ('classic', 'minimal', 'profile'):
            with self.subTest(template=template):
                content = {**self.card.draft, 'template':template, 'videos':videos}
                save_card(self.user, self.card.pk, self.card.draft_version, content)
                self.card.refresh_from_db()
                publish_card(self.user, self.card.pk, self.card.draft_version)
                response = Client().get(f'/c/{self.card.public_id}')
                self.assertContains(response, 'class="video-slide"', count=2)
                self.assertContains(response, '<iframe', count=1)
                self.assertContains(response, 'https://ok.ru/videoembed/123456789')
        for invalid in ([{'url':'javascript:alert(1)'}], videos*11, [{'title':'Нет ссылки'}]):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                validate_content({**self.card.draft, 'videos':invalid}, workspace=self.space)
