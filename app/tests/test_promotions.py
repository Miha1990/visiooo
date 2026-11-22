from datetime import timedelta
from unittest.mock import patch
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from billing import services
from billing.models import AccessGrant, Payment, PromoCode, Subscription
from billing.promotions import grant_access, redeem, revoke_access
from cards.services import create_card, publish_card
from workspaces.models import Membership, Workspace


@override_settings(YOOKASSA_ENABLED=False, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class PromotionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('admin-promo@example.test')
        cls.user = User.objects.create_user('promo@example.test', email_verified_at=timezone.now())
        cls.workspace = Workspace.objects.create(owner=cls.user)
        Membership.objects.create(user=cls.user, workspace=cls.workspace)
        cls.sub = Subscription.objects.create(workspace=cls.workspace)

    def setUp(self):
        cache.clear()
        self.client.force_login(self.user)

    def test_manual_grant_works_without_payments_and_unlocks_publication(self):
        grant = grant_access(self.admin, self.user, days=7, note='Партнёр')
        self.assertEqual(grant.issued_by, self.admin)
        self.assertTrue(self.sub.is_active)
        self.assertIsNone(self.sub.paid_until)
        self.assertEqual(self.sub.access_until, grant.ends_at)
        for _ in range(3):
            card = create_card(self.user)
        with self.assertRaises(ValidationError):
            create_card(self.user)
        publish_card(self.user, card.pk, card.draft_version)
        self.assertEqual(self.client.get(f'/c/{card.public_id}').status_code, 200)
        self.assertFalse(Payment.objects.exists())

    def test_permanent_access_and_checkout_block(self):
        grant = grant_access(self.admin, self.user, permanent=True)
        self.assertIsNone(grant.ends_at)
        self.assertTrue(self.sub.is_permanent)
        self.assertTrue(self.sub.is_active)
        response = self.client.get('/app/subscription')
        self.assertContains(response, 'бессрочный доступ')
        self.assertNotContains(response, 'name="token"')
        self.assertEqual(self.client.post('/app/subscription/checkout', {}).status_code, 422)

    def test_grants_stack_after_paid_period_and_revocation_preserves_payment(self):
        paid_until = timezone.now() + timedelta(days=20)
        self.sub.status, self.sub.paid_until = 'active', paid_until
        self.sub.save()
        first = grant_access(self.admin, self.user, days=7)
        second = grant_access(self.admin, self.user, days=3)
        self.assertEqual(first.ends_at, paid_until + timedelta(days=7))
        self.assertEqual(second.ends_at, paid_until + timedelta(days=10))
        revoke_access(self.admin, second.pk)
        self.assertEqual(self.sub.access_until, first.ends_at)
        revoke_access(self.admin, first.pk)
        self.assertEqual(self.sub.access_until, paid_until)
        self.assertTrue(self.sub.is_active)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.paid_until, paid_until)

    def test_expired_and_revoked_grants_stop_access(self):
        grant = grant_access(self.admin, self.user, days=1)
        AccessGrant.objects.filter(pk=grant.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(self.sub.is_active)
        grant = grant_access(self.admin, self.user, permanent=True)
        self.assertTrue(revoke_access(self.admin, grant.pk))
        self.assertFalse(revoke_access(self.admin, grant.pk))
        self.assertFalse(self.sub.is_active)
        grant.refresh_from_db()
        self.assertEqual(grant.revoked_by, self.admin)

    def test_permissions_on_manual_grant_and_revocation(self):
        with self.assertRaises(PermissionDenied):
            grant_access(self.user, self.user)
        grant = grant_access(self.admin, self.user)
        with self.assertRaises(PermissionDenied):
            revoke_access(self.user, grant.pk)

    def test_promo_case_normalization_and_once_per_account(self):
        promo = PromoCode.objects.create(code='PARTNER30', days=30, max_uses=None)
        grant = redeem(self.user, ' partner30 ')
        self.assertEqual(grant.promo, promo)
        self.assertTrue(self.sub.is_active)
        with self.assertRaises(ValidationError):
            redeem(self.user, 'PARTNER30')
        revoke_access(self.admin, grant.pk)
        with self.assertRaises(ValidationError):
            redeem(self.user, 'PARTNER30')
        self.assertEqual(promo.uses, 1)
        self.assertFalse(Payment.objects.exists())

    def test_rejects_disabled_expired_future_restricted_and_exhausted_codes(self):
        for number, fields in enumerate([
            {'active': False}, {'expires_at': timezone.now() - timedelta(seconds=1)},
            {'starts_at': timezone.now() + timedelta(days=1)}, {'email': 'someone@example.test'},
        ]):
            promo = PromoCode.objects.create(code=f'NOPE{number}', **fields)
            with self.assertRaises(ValidationError):
                redeem(self.user, promo.code)
        with self.assertRaises(ValidationError):
            redeem(self.user, 'missing')
        with self.assertRaises(ValidationError):
            redeem(self.user, '<bad>')
        self.assertFalse(AccessGrant.objects.exists())

    def test_personal_promo_and_unverified_account(self):
        promo = PromoCode.objects.create(code='PERSONAL', email='PROMO@EXAMPLE.TEST')
        self.user.email_verified_at = None
        self.user.save()
        with self.assertRaises(ValidationError):
            redeem(self.user, promo.code)
        self.user.email_verified_at = timezone.now()
        self.user.save()
        redeem(self.user, promo.code)
        self.assertEqual(promo.uses, 1)

    def test_permanent_account_does_not_consume_promo(self):
        grant_access(self.admin, self.user, permanent=True)
        promo = PromoCode.objects.create(code='KEEPTHIS')
        with self.assertRaises(ValidationError):
            redeem(self.user, promo.code)
        self.assertEqual(promo.uses, 0)

    def test_redemption_route_csrf_auth_get_and_rate_limit(self):
        promo = PromoCode.objects.create(code='WEBPROMO')
        anonymous = Client()
        self.assertEqual(anonymous.post('/app/subscription/promo', {'code': promo.code}).status_code, 302)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.user)
        self.assertEqual(secured.post('/app/subscription/promo', {'code': promo.code}).status_code, 403)
        self.assertEqual(self.client.get('/app/subscription/promo').status_code, 405)
        self.assertEqual(self.client.post('/app/subscription/promo', {'code': promo.code})['Location'], '/app/subscription')
        self.assertContains(self.client.get('/app/subscription'), 'Промокод активирован')
        for _ in range(9):
            self.client.post('/app/subscription/promo', {'code': 'BADCODE'})
        self.assertEqual(self.client.post('/app/subscription/promo', {'code': 'BADCODE'}).status_code, 429)
        self.assertEqual(promo.uses, 1)

    def test_paid_renewal_starts_after_free_access_and_applies_once(self):
        grant = grant_access(self.admin, self.user, days=10)
        payment = Payment.objects.create(workspace=self.workspace, user=self.user, period='month',
            amount='199.00', shop_id='shop', test=True)
        data = {'id': 'provider-promo-renewal', 'status': 'succeeded', 'paid': True, 'test': True,
            'amount': {'value': '199.00', 'currency': 'RUB'}, 'recipient': {'account_id': 'shop'},
            'metadata': {'order_id': str(payment.pk), 'workspace_id': str(self.workspace.pk)}}
        with override_settings(YOOKASSA_SHOP_ID='shop', YOOKASSA_TEST_MODE=True):
            services.apply(payment.pk, data)
            services.apply(payment.pk, data)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.paid_until, services.add_months(grant.ends_at, 1))
        revoke_access(self.admin, grant.pk)
        self.assertTrue(self.sub.is_active)

    def test_admin_grant_form_and_promo_controls(self):
        self.client.force_login(self.admin)
        for path in ('/admin/billing/accessgrant/add/', '/admin/billing/promocode/add/', '/admin/billing/subscription/'):
            self.assertEqual(self.client.get(path).status_code, 200)
        response = self.client.post('/admin/billing/accessgrant/add/', {
            'user': str(self.user.pk), 'days': '14', 'note': 'Партнёрский доступ', '_save': 'Сохранить'})
        self.assertEqual(response.status_code, 302)
        grant = AccessGrant.objects.get()
        self.assertEqual(grant.issued_by, self.admin)
        self.assertEqual(grant.days, 14)
        self.assertEqual(self.client.get(f'/admin/billing/accessgrant/{grant.pk}/change/').status_code, 200)
        response = self.client.post('/admin/billing/promocode/add/', {
            'code': ' admin-code ', 'days': '3', 'active': 'on', 'starts_at_0': '2026-01-01',
            'starts_at_1': '00:00:00', 'max_uses': '2', '_save': 'Сохранить'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PromoCode.objects.filter(code='ADMIN-CODE').exists())

    def test_admin_can_revoke_without_erasing_history(self):
        grant = grant_access(self.admin, self.user, permanent=True)
        self.client.force_login(self.admin)
        self.client.post('/admin/billing/accessgrant/', {'action': 'revoke_selected', '_selected_action': str(grant.pk)})
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoked_at)
        self.assertFalse(self.sub.is_active)

    def test_max_uses_shared_between_accounts(self):
        promo = PromoCode.objects.create(code='LIMITONE', max_uses=1)
        redeem(self.user, promo.code)
        user = User.objects.create_user('second-promo@example.test', email_verified_at=timezone.now())
        workspace = Workspace.objects.create(owner=user)
        Membership.objects.create(user=user, workspace=workspace)
        with self.assertRaises(ValidationError):
            redeem(user, promo.code)
        self.assertEqual(promo.uses, 1)

    def test_grant_creation_rolls_back_with_outer_transaction(self):
        from django.db import transaction
        promo = PromoCode.objects.create(code='ROLLBACK')
        with self.assertRaises(RuntimeError), transaction.atomic():
            redeem(self.user, promo.code)
            raise RuntimeError('rollback')
        self.assertFalse(AccessGrant.objects.exists())
        self.assertEqual(promo.uses, 0)
