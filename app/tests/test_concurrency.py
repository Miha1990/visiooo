from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from django.core.exceptions import ValidationError
from django.db import connection, connections, close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone
from accounts.models import User
from billing.models import Subscription
from workspaces.models import Workspace, Membership
from cards.models import Card
from cards.services import create_card, save_card, Conflict


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
class ConcurrentRequestsTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user('parallel@example.test', 'Parallel-927!')
        self.workspace = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.workspace)
        Subscription.objects.create(workspace=self.workspace, status='active',
                                    paid_until=timezone.now() + timedelta(days=1))

    def parallel(self, operation):
        barrier = Barrier(2)

        def run(index):
            close_old_connections()
            try:
                user = User.objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                return operation(user, index)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, [0, 1]))

    def test_parallel_creation_cannot_exceed_quota(self):
        create_card(self.user)
        create_card(self.user)

        def operation(user, index):
            try:
                create_card(user)
                return 'created'
            except ValidationError:
                return 'limited'
        self.assertCountEqual(self.parallel(operation), ['created', 'limited'])
        self.assertEqual(Card.objects.filter(workspace=self.workspace).count(), 3)

    def test_parallel_edits_exactly_one_wins(self):
        card = create_card(self.user)

        def operation(user, index):
            try:
                save_card(user, card.pk, 1, dict(card.draft, name=f'Version {index}'))
                return 'saved'
            except Conflict:
                return 'conflict'
        self.assertCountEqual(self.parallel(operation), ['saved', 'conflict'])
        card.refresh_from_db()
        self.assertEqual(card.draft_version, 2)

    def payment_data(self, payment):
        return {'id': 'provider-' + str(payment.pk), 'status': 'succeeded', 'paid': True, 'test': True,
                'amount': {'value': str(payment.amount), 'currency': 'RUB'},
                'recipient': {'account_id': 'parallel-shop'},
                'metadata': {'order_id': str(payment.pk), 'workspace_id': str(self.workspace.pk)}}

    def test_parallel_payment_notifications_extend_once(self):
        from billing.models import Payment
        from billing.services import apply, add_months
        from django.test import override_settings
        subscription = Subscription.objects.get(workspace=self.workspace)
        previous = subscription.paid_until
        payment = Payment.objects.create(workspace=self.workspace, user=self.user, period='month',
            amount='199.00', shop_id='parallel-shop', test=True)
        with override_settings(YOOKASSA_SHOP_ID='parallel-shop', YOOKASSA_TEST_MODE=True):
            self.parallel(lambda user, index: apply(payment.pk, self.payment_data(payment)).status)
        subscription.refresh_from_db()
        self.assertEqual(subscription.paid_until, add_months(previous, 1))
        self.assertEqual(Payment.objects.filter(applied_at__isnull=False).count(), 1)

    def test_different_parallel_payments_preserve_both_periods(self):
        from billing.models import Payment
        from billing.services import apply, add_months
        from django.test import override_settings
        subscription = Subscription.objects.get(workspace=self.workspace)
        previous = subscription.paid_until
        payments = [Payment.objects.create(workspace=self.workspace, user=self.user, period='month',
            amount='199.00', shop_id='parallel-shop', test=True) for _ in range(2)]
        with override_settings(YOOKASSA_SHOP_ID='parallel-shop', YOOKASSA_TEST_MODE=True):
            self.parallel(lambda user, index: apply(payments[index].pk, self.payment_data(payments[index])).status)
        subscription.refresh_from_db()
        self.assertEqual(subscription.paid_until, add_months(add_months(previous, 1), 1))
        self.assertEqual(Payment.objects.filter(applied_at__isnull=False).count(), 2)

    def test_parallel_physical_rebinding_has_one_winner(self):
        from cards.physical import create_physical, update_physical
        cards = [create_card(self.user), create_card(self.user)]
        item = create_physical(self.user, 'Physical', cards[0])

        def operation(user, index):
            try:
                update_physical(user, item.pk, 1, 'Physical', cards[index])
                return 'bound'
            except Conflict:
                return 'conflict'
        self.assertCountEqual(self.parallel(operation), ['bound', 'conflict'])
        item.refresh_from_db()
        self.assertEqual(item.version, 2)

    def test_parallel_domain_creation_cannot_bypass_workspace_limit(self):
        from domains.services import add_domain
        from domains.models import DomainBinding
        card = create_card(self.user)

        def operation(user, index):
            try:
                add_domain(user, f'parallel-{index}.example.com', card)
                return 'added'
            except ValidationError:
                return 'limited'
        self.assertCountEqual(self.parallel(operation), ['added', 'limited'])
        self.assertEqual(DomainBinding.objects.filter(workspace=self.workspace).count(), 1)

    def test_parallel_upload_cannot_exceed_storage_quota(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        from cards.images import normalize_image, upload_avatar
        from cards.models import Asset
        from .test_images import photo
        cards = [create_card(self.user), create_card(self.user)]
        data, _, _ = normalize_image(photo())
        occupied = Asset.objects.create(workspace=self.workspace, object_key='quota-test.webp',
            bytes=50 * 1024 * 1024 - len(data), width=1, height=1)
        quota_card = create_card(self.user)
        save_card(self.user, quota_card.pk, 1, dict(quota_card.draft, headerAssetId=str(occupied.pk)))

        def operation(user, index):
            try:
                upload_avatar(user, cards[index].pk, 1, photo())
                return 'uploaded'
            except ValidationError:
                return 'limited'
        with TemporaryDirectory() as directory, override_settings(PRIVATE_MEDIA_ROOT=Path(directory)):
            self.assertCountEqual(self.parallel(operation), ['uploaded', 'limited'])
            self.assertEqual(len(list(Path(directory).rglob('*.webp'))), 1)

    def test_parallel_password_resets_only_one_token_succeeds(self):
        from django.test import Client
        from accounts.models import PasswordResetToken
        from accounts.password_reset import digest
        tokens = ['concurrent-reset-one', 'concurrent-reset-two']
        for token in tokens:
            PasswordResetToken.objects.create(user=self.user, digest=digest(token),
                credential_digest=digest(self.user.password), expires_at=timezone.now() + timedelta(hours=1))

        def operation(user, index):
            return Client().post('/accounts/password-reset/' + tokens[index], {
                'new_password1': f'ParallelNewPassword-{index}-284!',
                'new_password2': f'ParallelNewPassword-{index}-284!'}).status_code
        self.assertCountEqual(self.parallel(operation), [303, 400])
        self.assertEqual(PasswordResetToken.objects.filter(used_at__isnull=False).count(), 1)

    def test_cleanup_and_attaching_legacy_asset_cannot_leave_a_broken_reference(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        from cards.asset_cleanup import cleanup_unused_assets
        from cards.images import upload_avatar, private_storage
        from cards.models import Asset
        from .test_images import photo
        card = create_card(self.user)
        with TemporaryDirectory() as directory, override_settings(PRIVATE_MEDIA_ROOT=Path(directory)):
            asset = upload_avatar(self.user, card.pk, 1, photo())
            card.refresh_from_db()
            content = dict(card.draft)
            content.pop('avatarAssetId')
            Card.objects.filter(pk=card.pk).update(draft=content)

            def operation(user, index):
                if index == 0:
                    cleanup_unused_assets(self.workspace.pk)
                    return 'cleaned'
                try:
                    save_card(user, card.pk, card.draft_version, dict(content, avatarAssetId=str(asset.pk)))
                    return 'attached'
                except ValidationError:
                    return 'gone'

            result = self.parallel(operation)
            card.refresh_from_db()
            attached = 'attached' in result
            self.assertEqual(card.draft.get('avatarAssetId'), str(asset.pk) if attached else None)
            self.assertEqual(Asset.objects.filter(pk=asset.pk).exists(), attached)
            self.assertEqual(private_storage().exists(asset.object_key), attached)
