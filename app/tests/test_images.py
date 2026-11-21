from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from billing.models import Subscription
from workspaces.models import Workspace, Membership
from cards.forms import CardForm
from cards.images import normalize_image, upload_avatar, remove_avatar
from cards.models import Asset
from cards.services import create_card, publish_card, save_card, Conflict


def photo(format='PNG', size=(80, 60), metadata=False):
    output = BytesIO()
    image = Image.new('RGB', size, '#435b75')
    kwargs = {}
    if metadata:
        exif = Image.Exif()
        exif[270] = 'Private image description'
        exif[274] = 6
        kwargs['exif'] = exif
    image.save(output, format, **kwargs)
    return SimpleUploadedFile('untrusted-name.jpg', output.getvalue(), content_type='image/jpeg')


class ImageTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(PRIVATE_MEDIA_ROOT=Path(self.directory.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = User.objects.create_user('photo@example.test', 'PhotoSecret-921!', email_verified_at=timezone.now())
        self.workspace = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.workspace)
        self.sub = Subscription.objects.create(workspace=self.workspace, status='active',
            paid_until=timezone.now() + timedelta(days=1))
        self.card = create_card(self.user)
        self.client.force_login(self.user)

    def upload(self, image=None):
        self.card.refresh_from_db()
        asset = upload_avatar(self.user, self.card.pk, self.card.draft_version, image or photo())
        self.card.refresh_from_db()
        return asset

    def public_url(self, asset):
        return reverse('public_asset', args=[self.card.public_id, asset.pk])

    def test_reencode_strips_metadata_and_applies_orientation(self):
        data, width, height = normalize_image(photo('JPEG', metadata=True))
        self.assertEqual((width, height), (60, 80))
        with Image.open(BytesIO(data)) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertEqual(dict(image.getexif()), {})
            self.assertNotIn('exif', image.info)
            self.assertNotIn('icc_profile', image.info)
        self.assertNotIn(b'Private image description', data)

    def test_actual_format_validated_not_filename_or_mime(self):
        invalid = [SimpleUploadedFile('photo.png', b'<svg><script>alert(1)</script></svg>', content_type='image/png'),
                   photo('GIF'), SimpleUploadedFile('broken.jpg', b'\xff\xd8\xffbroken', content_type='image/jpeg')]
        for upload in invalid:
            with self.subTest(name=upload.name), self.assertRaises(ValidationError):
                normalize_image(upload)

    def test_file_and_pixel_limits(self):
        with self.assertRaises(ValidationError):
            normalize_image(SimpleUploadedFile('big.png', b'x' * (5 * 1024 * 1024 + 1)))
        with self.assertRaises(ValidationError):
            normalize_image(photo(size=(4500, 4500)))

    def test_thumbnail_size_and_alpha(self):
        asset = self.upload(photo(size=(2000, 1000)))
        self.assertEqual((asset.width, asset.height), (1600, 800))
        self.assertTrue(asset.object_key.endswith('.webp'))
        self.assertNotIn('untrusted-name', asset.object_key)

    def test_animation_rejected(self):
        output = BytesIO()
        frames = [Image.new('RGB', (10, 10), color) for color in ('red', 'blue')]
        frames[0].save(output, 'WEBP', save_all=True, append_images=frames[1:], duration=100, loop=0)
        with self.assertRaises(ValidationError):
            normalize_image(SimpleUploadedFile('animation.webp', output.getvalue()))

    def test_snapshot_controls_photo_visibility_and_replacement(self):
        first = self.upload()
        self.assertEqual(self.client.get(self.public_url(first)).status_code, 404)
        preview_url = reverse('preview_asset', args=[self.card.pk, first.pk])
        response = self.client.get(preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        b''.join(response.streaming_content)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        second = self.upload()
        response = self.client.get(self.public_url(first))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        self.assertEqual(self.client.get(self.public_url(second)).status_code, 404)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assertEqual(self.client.get(self.public_url(first)).status_code, 404)
        response = self.client.get(self.public_url(second))
        self.assertEqual(response['Content-Type'], 'image/webp')
        b''.join(response.streaming_content)

    def test_unpublish_block_expiry_delete_close_photo(self):
        asset = self.upload()
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.sub.paid_until = timezone.now() - timedelta(seconds=1)
        self.sub.save()
        self.assertEqual(self.client.get(self.public_url(asset)).status_code, 404)
        self.sub.paid_until = timezone.now() + timedelta(days=1)
        self.sub.save()
        from cards.models import Card
        Card.objects.filter(pk=self.card.pk).update(blocked=True)
        self.assertEqual(self.client.get(self.public_url(asset)).status_code, 404)
        Card.objects.filter(pk=self.card.pk).update(blocked=False)
        self.client.post(reverse('unpublish', args=[self.card.pk]))
        self.assertEqual(self.client.get(self.public_url(asset)).status_code, 404)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.client.post(reverse('delete', args=[self.card.pk]))
        self.assertEqual(self.client.get(self.public_url(asset)).status_code, 404)
        self.assertEqual(self.client.get(reverse('preview_asset', args=[self.card.pk, asset.pk])).status_code, 404)

    def test_foreign_asset_rejected_and_preview_is_private(self):
        asset = self.upload()
        other = User.objects.create_user('other-photo@example.test', 'OtherPhoto-482!')
        space = Workspace.objects.create(owner=other)
        Membership.objects.create(user=other, workspace=space)
        Subscription.objects.create(workspace=space)
        other_card = create_card(other)
        with self.assertRaises(ValidationError):
            save_card(other, other_card.pk, 1, dict(other_card.draft, avatarAssetId=str(asset.pk)))
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('preview_asset', args=[self.card.pk, asset.pk])).status_code, 404)
        self.assertEqual(self.client.post('/app/assets', {'card_id': self.card.pk,
            'draft_version': self.card.draft_version, 'image': photo()}).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('preview_asset', args=[self.card.pk, asset.pk])).status_code, 302)

    def test_storage_quota_and_cleanup_after_failed_save(self):
        Asset.objects.create(workspace=self.workspace, object_key='not-a-real-file.webp', bytes=50 * 1024 * 1024,
                             width=1, height=1)
        with self.assertRaises(ValidationError):
            self.upload()
        self.assertEqual(list(Path(self.directory.name).rglob('*.webp')), [])
        Asset.objects.all().delete()
        with patch('cards.images.save_card', side_effect=Conflict('stale')), self.assertRaises(Conflict):
            self.upload()
        self.assertEqual(Asset.objects.count(), 0)
        self.assertEqual(list(Path(self.directory.name).rglob('*.webp')), [])

    def test_unpaid_storage_quota(self):
        self.sub.status = 'pending'
        self.sub.save()
        Asset.objects.create(workspace=self.workspace, object_key='unused.webp', bytes=10 * 1024 * 1024,
                             width=1, height=1)
        with self.assertRaises(ValidationError):
            self.upload()

    def test_remove_preserves_published_image_until_republication(self):
        asset = self.upload()
        publish_card(self.user, self.card.pk, self.card.draft_version)
        remove_avatar(self.user, self.card.pk, self.card.draft_version)
        response = self.client.get(self.public_url(asset))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        self.card.refresh_from_db()
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assertEqual(self.client.get(self.public_url(asset)).status_code, 404)

    def test_upload_route_errors_and_version_conflict(self):
        self.assertEqual(self.client.post('/app/assets', {}).status_code, 422)
        self.assertEqual(self.client.post('/app/assets', {'card_id': self.card.pk,
            'draft_version': 1, 'image': photo()}).status_code, 303)
        response = self.client.post('/app/assets', {'card_id': self.card.pk,
            'draft_version': 1, 'image': photo()})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Asset.objects.count(), 1)

    def test_templates_and_avatar_survive_form_save(self):
        asset = self.upload()
        for template in ['classic', 'minimal', 'profile']:
            self.card.refresh_from_db()
            form = CardForm.for_card(self.card, {'name': 'Анна', 'template': template, 'accent': '#2457DB',
                'links': '', 'draft_version': self.card.draft_version})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.content['avatarAssetId'], str(asset.pk))
            save_card(self.user, self.card.pk, self.card.draft_version, form.content)
            self.card.refresh_from_db()
            publish_card(self.user, self.card.pk, self.card.draft_version)
            response = self.client.get(reverse('public', args=[self.card.public_id]))
            self.assertContains(response, f'template-{template}')
            self.assertContains(response, self.public_url(asset))
            response = self.client.get(reverse('edit', args=[self.card.pk]))
            self.assertContains(response, f'template-{template}')
            self.assertContains(response, reverse('preview_asset', args=[self.card.pk, asset.pk]))

    def test_background_upload_keeps_avatar_and_published_snapshot(self):
        avatar = self.upload()
        background = upload_avatar(self.user, self.card.pk, self.card.draft_version, photo(), target='background')
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['avatarAssetId'], str(avatar.pk))
        self.assertEqual(self.card.draft['backgroundAssetId'], str(background.pk))
        self.assertEqual(self.client.get(self.public_url(background)).status_code, 404)
        response = self.client.get(reverse('preview_asset', args=[self.card.pk, background.pk]))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        second = upload_avatar(self.user, self.card.pk, self.card.draft_version, photo(), target='background')
        self.card.refresh_from_db()
        response = self.client.get(self.public_url(background))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        self.assertEqual(self.client.get(self.public_url(second)).status_code, 404)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assertEqual(self.client.get(self.public_url(background)).status_code, 404)
        response = self.client.get(self.public_url(second))
        self.assertIn('no-store', response['Cache-Control'])
        b''.join(response.streaming_content)

    def test_background_removal_is_independent_and_waits_for_publication(self):
        avatar = self.upload()
        background = upload_avatar(self.user, self.card.pk, self.card.draft_version, photo(), target='background')
        self.card.refresh_from_db()
        publish_card(self.user, self.card.pk, self.card.draft_version)
        response = self.client.post(reverse('remove_avatar', args=[self.card.pk]), {
            'draft_version': self.card.draft_version, 'target': 'background'})
        self.assertEqual(response.status_code, 303)
        self.card.refresh_from_db()
        self.assertNotIn('backgroundAssetId', self.card.draft)
        self.assertEqual(self.card.draft['avatarAssetId'], str(avatar.pk))
        response = self.client.get(self.public_url(background))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assertEqual(self.client.get(self.public_url(background)).status_code, 404)

    def test_background_form_save_and_render_all_templates(self):
        background = upload_avatar(self.user, self.card.pk, 1, photo(), target='background')
        self.card.refresh_from_db()
        for template in ['classic', 'minimal', 'profile']:
            form = CardForm.for_card(self.card, {'name': 'Анна', 'template': template, 'accent': '#2457DB',
                'draft_version': self.card.draft_version, 'links': ''})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.content['backgroundAssetId'], str(background.pk))
            save_card(self.user, self.card.pk, self.card.draft_version, form.content)
            self.card.refresh_from_db()
            publish_card(self.user, self.card.pk, self.card.draft_version)
            response = self.client.get(reverse('public', args=[self.card.public_id]))
            self.assertContains(response, f'template-{template} has-background')
            self.assertContains(response, self.public_url(background))

    def test_background_cannot_reference_foreign_photo_or_bypass_expiry(self):
        from cards.validation import validate_content
        background = upload_avatar(self.user, self.card.pk, 1, photo(), target='background')
        self.card.refresh_from_db()
        with self.assertRaises(ValidationError):
            validate_content(self.card.draft, workspace=None)
        other = Workspace.objects.create(owner=User.objects.create_user('bg-other@example.test', 'OtherBgPassword-281!'))
        with self.assertRaises(ValidationError):
            validate_content(self.card.draft, workspace=other)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.sub.paid_until = timezone.now() - timedelta(seconds=1)
        self.sub.save()
        self.assertEqual(self.client.get(self.public_url(background)).status_code, 404)

    def test_background_upload_route_validates_target_and_stale_version(self):
        response = self.client.post('/app/assets', {'card_id': self.card.pk, 'draft_version': 1,
            'target': 'background', 'image': photo()})
        self.assertEqual(response.status_code, 303)
        self.card.refresh_from_db()
        self.assertIn('backgroundAssetId', self.card.draft)
        self.assertNotIn('avatarAssetId', self.card.draft)
        self.assertEqual(self.client.post('/app/assets', {'card_id': self.card.pk, 'draft_version': 1,
            'target': 'background', 'image': photo()}).status_code, 409)
        self.assertEqual(self.client.post('/app/assets', {'card_id': self.card.pk,
            'draft_version': self.card.draft_version, 'target': '../../unsafe', 'image': photo()}).status_code, 422)
        self.assertEqual(Asset.objects.count(), 1)

    def test_three_independent_images_survive_saving_and_render_in_all_templates(self):
        from cards.image_slots import IMAGE_FIELDS
        images = {}
        for target, field in IMAGE_FIELDS.items():
            self.card.refresh_from_db()
            images[field] = upload_avatar(self.user, self.card.pk, self.card.draft_version, photo(), target=target)
        self.card.refresh_from_db()
        self.assertEqual(len({str(asset.pk) for asset in images.values()}), 3)
        for template in ('classic', 'minimal', 'profile'):
            form = CardForm.for_card(self.card, {'name': 'Анна', 'template': template, 'accent': '#2457DB',
                'draft_version': self.card.draft_version, 'links': ''})
            self.assertTrue(form.is_valid(), form.errors)
            for field, asset in images.items():
                self.assertEqual(form.content[field], str(asset.pk))
            save_card(self.user, self.card.pk, self.card.draft_version, form.content)
            self.card.refresh_from_db()
            publish_card(self.user, self.card.pk, self.card.draft_version)
            response = self.client.get(reverse('public', args=[self.card.public_id]))
            self.assertContains(response, f'template-{template} has-background has-header')
            for asset in images.values():
                self.assertContains(response, self.public_url(asset))
            self.assertContains(response, 'class="cover-photo"')
            self.assertContains(response, 'class="card-background"')
            self.assertContains(response, 'class="contact-avatar avatar-photo"')

    def test_replacing_and_removing_header_leaves_other_images_and_snapshot_intact(self):
        from cards.image_slots import IMAGE_FIELDS
        assets = {}
        for target in IMAGE_FIELDS:
            self.card.refresh_from_db()
            assets[target] = upload_avatar(self.user, self.card.pk, self.card.draft_version, photo(), target=target)
        self.card.refresh_from_db()
        publish_card(self.user, self.card.pk, self.card.draft_version)
        replacement = upload_avatar(self.user, self.card.pk, self.card.draft_version, photo(), target='header')
        self.card.refresh_from_db()
        response = self.client.get(self.public_url(assets['header']))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        self.assertEqual(self.client.get(self.public_url(replacement)).status_code, 404)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assertEqual(self.client.get(self.public_url(assets['header'])).status_code, 404)
        response = self.client.post(reverse('remove_avatar', args=[self.card.pk]), {
            'target': 'header', 'draft_version': self.card.draft_version})
        self.assertEqual(response.status_code, 303)
        self.card.refresh_from_db()
        self.assertNotIn('headerAssetId', self.card.draft)
        self.assertEqual(self.card.draft['avatarAssetId'], str(assets['avatar'].pk))
        self.assertEqual(self.card.draft['backgroundAssetId'], str(assets['background'].pk))
        response = self.client.get(self.public_url(replacement))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assertEqual(self.client.get(self.public_url(replacement)).status_code, 404)

    def test_header_route_and_owner_preview_protect_unpublished_image(self):
        response = self.client.post('/app/assets', {'card_id': self.card.pk, 'draft_version': 1,
            'target': 'header', 'image': photo()})
        self.assertEqual(response.status_code, 303)
        self.card.refresh_from_db()
        asset = Asset.objects.get(pk=self.card.draft['headerAssetId'])
        response = self.client.get(reverse('preview_asset', args=[self.card.pk, asset.pk]))
        self.assertEqual(response.status_code, 200)
        b''.join(response.streaming_content)
        self.assertEqual(self.client.get(self.public_url(asset)).status_code, 404)
        self.assertEqual(self.client.post('/app/assets', {'card_id': self.card.pk, 'draft_version': 1,
            'target': 'header', 'image': photo()}).status_code, 409)
        self.assertEqual(Asset.objects.count(), 1)

    def test_foreign_header_asset_rejected_and_expired_subscription_hides_header(self):
        from cards.validation import validate_content
        asset = upload_avatar(self.user, self.card.pk, 1, photo(), target='header')
        self.card.refresh_from_db()
        other = Workspace.objects.create(owner=User.objects.create_user('header-other@example.test', 'OtherHeader-291!'))
        with self.assertRaises(ValidationError):
            validate_content(self.card.draft, workspace=other)
        publish_card(self.user, self.card.pk, self.card.draft_version)
        self.sub.paid_until = timezone.now() - timedelta(seconds=1)
        self.sub.save()
        self.assertEqual(self.client.get(self.public_url(asset)).status_code, 404)

    def test_editor_has_three_ordered_controls_with_unique_field_ids(self):
        response = self.client.get(reverse('edit', args=[self.card.pk]))
        self.assertContains(response, 'data-image-slot="background"')
        self.assertContains(response, 'data-image-slot="avatar"')
        self.assertContains(response, 'data-image-slot="header"')
        html = response.content.decode()
        self.assertLess(html.index('data-image-slot="background"'), html.index('data-image-slot="avatar"'))
        self.assertLess(html.index('data-image-slot="avatar"'), html.index('data-image-slot="header"'))
        for target in ('background', 'avatar', 'header'):
            self.assertContains(response, f'id="{target}_image"', count=1)
