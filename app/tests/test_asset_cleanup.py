from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from billing.models import Subscription
from workspaces.models import Membership, Workspace
from cards.asset_cleanup import cleanup_unused_assets
from cards.images import private_storage, remove_avatar, upload_avatar
from cards.models import Asset
from cards.services import create_card, delete_card, publish_card, save_card, unpublish_card, Conflict
from .test_images import photo


class AssetCleanupTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(PRIVATE_MEDIA_ROOT=Path(directory.name))
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user('cleanup@example.test', 'CleanupPassword-512!', email_verified_at=timezone.now())
        self.workspace = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.workspace)
        self.subscription = Subscription.objects.create(workspace=self.workspace, status='active',
            paid_until=timezone.now() + timedelta(days=1))
        self.card = create_card(self.user)

    def upload(self, target='avatar'):
        self.card.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            asset = upload_avatar(self.user, self.card.pk, self.card.draft_version, photo(), target=target)
        self.card.refresh_from_db()
        return asset

    def assert_present(self, asset, present=True):
        self.assertEqual(Asset.objects.filter(pk=asset.pk).exists(), present)
        self.assertEqual(private_storage().exists(asset.object_key), present)

    def test_replacement_cleans_each_slot_independently(self):
        assets = {slot: self.upload(slot) for slot in ('background', 'avatar', 'header')}
        for slot in assets:
            previous = assets[slot]
            assets[slot] = self.upload(slot)
            self.assert_present(previous, False)
            for retained in assets.values():
                self.assert_present(retained)
        self.assertEqual(Asset.objects.count(), 3)

    def test_published_photo_retained_until_republication_even_if_hidden(self):
        original = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            publish_card(self.user, self.card.pk, self.card.draft_version)
            remove_avatar(self.user, self.card.pk, self.card.draft_version)
        unpublish_card(self.user, self.card.pk)
        self.subscription.status = 'pending'
        self.subscription.save()
        cleanup_unused_assets(self.workspace.pk)
        self.assert_present(original)
        self.subscription.status = 'active'
        self.subscription.save()
        self.card.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            publish_card(self.user, self.card.pk, self.card.draft_version)
        self.assert_present(original, False)
        # Historical snapshots keep the original content, but no longer reserve disk space.
        self.assertEqual(self.card.revisions.count(), 2)

    def test_shared_photo_not_removed_until_last_card_is_deleted(self):
        asset = self.upload()
        other = create_card(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            save_card(self.user, other.pk, 1, dict(other.draft, headerAssetId=str(asset.pk)))
            delete_card(self.user, self.card.pk)
        self.assert_present(asset)
        with self.captureOnCommitCallbacks(execute=True):
            delete_card(self.user, other.pk)
        self.assert_present(asset, False)

    def test_removal_and_card_deletion_release_files(self):
        avatar = self.upload()
        header = self.upload('header')
        with self.captureOnCommitCallbacks(execute=True):
            remove_avatar(self.user, self.card.pk, self.card.draft_version)
        self.assert_present(avatar, False)
        self.assert_present(header)
        with self.captureOnCommitCallbacks(execute=True):
            delete_card(self.user, self.card.pk)
        self.assert_present(header, False)

    def test_transaction_rollback_never_deletes_committed_photo(self):
        asset = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                remove_avatar(self.user, self.card.pk, self.card.draft_version)
                raise RuntimeError('rollback')
        self.card.refresh_from_db()
        self.assertEqual(self.card.draft['avatarAssetId'], str(asset.pk))
        self.assert_present(asset)

    def test_failed_upload_keeps_original_and_removes_new_file(self):
        asset = self.upload()
        with patch('cards.images.save_card', side_effect=Conflict('stale')), self.assertRaises(Conflict):
            self.upload()
        self.assert_present(asset)
        self.assertEqual(Asset.objects.count(), 1)
        self.assertEqual(len(list(Path(private_storage().location).rglob('*.webp'))), 1)

    def test_full_quota_allows_replacing_unpublished_photo(self):
        asset = self.upload()
        self.subscription.status = 'pending'
        self.subscription.save()
        Asset.objects.filter(pk=asset.pk).update(bytes=10 * 1024 * 1024)
        replacement = self.upload()
        self.assert_present(asset, False)
        self.assert_present(replacement)

    def test_full_quota_cannot_discard_published_photo_to_fit_replacement(self):
        asset = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            publish_card(self.user, self.card.pk, self.card.draft_version)
        Asset.objects.filter(pk=asset.pk).update(bytes=50 * 1024 * 1024)
        with self.assertRaises(ValidationError):
            self.upload()
        self.assert_present(asset)
        self.assertEqual(Asset.objects.count(), 1)

    def test_dry_run_and_retry_of_storage_failure(self):
        asset = self.upload()
        # Simulate a legacy orphan left by the previous version.
        self.card.draft.pop('avatarAssetId')
        self.card.save(update_fields=['draft'])
        output = StringIO()
        call_command('cleanup_unused_assets', dry_run=True, stdout=output)
        self.assertIn(str(asset.bytes), output.getvalue())
        self.assert_present(asset)
        with patch('django.core.files.storage.FileSystemStorage.delete', side_effect=PermissionError('locked')):
            with self.assertLogs('cards.asset_cleanup', level='WARNING'):
                result = cleanup_unused_assets(self.workspace.pk)
        self.assertEqual(result['failed'], 1)
        self.assert_present(asset)
        call_command('cleanup_unused_assets', stdout=StringIO())
        self.assert_present(asset, False)
        call_command('cleanup_unused_assets', stdout=StringIO())

    def test_cleanup_isolated_to_workspace(self):
        asset = self.upload()
        stranger = User.objects.create_user('other-cleanup@example.test', 'OtherCleanup-851!')
        workspace = Workspace.objects.create(owner=stranger)
        cleanup_unused_assets(workspace.pk)
        self.assert_present(asset)
