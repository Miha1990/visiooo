import hashlib
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch
from django.conf import settings
from django.core import signing
from django.test import TestCase, override_settings, Client
from django.utils import timezone
from accounts.models import User, LegalAcceptance
from billing.models import Payment, Subscription
from billing import services
from billing.gateway import GatewayError
from cards.services import create_card
from workspaces.models import Workspace, Membership


@override_settings(DEBUG=True, ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False,
    YOOKASSA_ENABLED=True, YOOKASSA_SHOP_ID='test-shop', YOOKASSA_SECRET_KEY='test-key',
    YOOKASSA_TEST_MODE=True, PUBLIC_BASE_URL='http://testserver')
class BillingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('buyer@example.test')
        self.user.email_verified_at = timezone.now(); self.user.save()
        self.workspace = Workspace.objects.create(owner=self.user)
        Membership.objects.create(user=self.user, workspace=self.workspace)
        self.sub = Subscription.objects.create(workspace=self.workspace)
        self.client.force_login(self.user)
        patcher = patch('billing.gateway.request', side_effect=AssertionError('Unexpected real API call'))
        self.api = patcher.start(); self.addCleanup(patcher.stop)

    def order(self, period='month'):
        return Payment.objects.create(workspace=self.workspace, user=self.user, period=period,
            amount=services.PRICES[period], shop_id='test-shop', test=True)

    def data(self, payment, status='succeeded'):
        result = {'id': payment.provider_id or 'provider-' + str(payment.pk), 'status': status,
            'paid': status == 'succeeded', 'test': True,
            'amount': {'value': str(payment.amount), 'currency': 'RUB'},
            'recipient': {'account_id': 'test-shop'},
            'metadata': {'order_id': str(payment.pk), 'workspace_id': str(self.workspace.pk)}}
        if status == 'pending':
            result['confirmation'] = {'confirmation_url': 'https://yoomoney.ru/checkout/payments/v2/contract?orderId=example'}
        return result

    def token(self, period='month'):
        import uuid
        return signing.dumps({'workspace': str(self.workspace.pk), 'period': period, 'id': str(uuid.uuid4())}, salt='checkout')

    def test_price_period_and_idempotence_are_server_owned(self):
        token = self.token('year')
        def response(method, path, payload=None, key=None):
            if method == 'POST':
                payment = Payment.objects.get(pk=payload['metadata']['order_id'])
                self.assertEqual(payload['amount'], {'value': '1490.00', 'currency': 'RUB'})
                self.assertTrue(payload['capture'])
                self.assertNotIn('save_payment_method', payload)
                self.assertEqual(str(key), str(payment.pk))
            else:
                payment = Payment.objects.get(provider_id=path.split('/')[-1])
            return self.data(payment, 'pending')
        self.api.side_effect = response
        for _ in range(2):
            result = self.client.post('/app/subscription/checkout', {'token': token,
                'offer': 'yes', 'processing': 'yes', 'amount': '0.01', 'period': 'month'})
            self.assertEqual(result.status_code, 303)
            self.assertTrue(result['Location'].startswith('https://yoomoney.ru/'))
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(LegalAcceptance.objects.count(), 2)
        self.assertEqual(self.api.call_args_list[0].args[0], 'POST')
        self.assertEqual(self.api.call_args_list[1].args[0], 'GET')

    def test_checkout_requires_two_separate_confirmations_and_verification(self):
        token = self.token()
        for posted in [{'offer': 'yes'}, {'processing': 'yes'}, {}]:
            self.assertEqual(self.client.post('/app/subscription/checkout', dict(token=token, **posted)).status_code, 422)
        self.user.email_verified_at = None; self.user.save()
        self.assertEqual(self.client.post('/app/subscription/checkout', {'token': token, 'offer': 'yes', 'processing': 'yes'}).status_code, 422)
        self.assertEqual(Payment.objects.count(), 0)
        self.api.assert_not_called()

    def test_unsigned_and_other_workspace_tokens_are_rejected(self):
        token = signing.dumps({'workspace': 'other', 'period': 'year', 'id': 'bad'}, salt='checkout')
        for value in [token, self.token()+'tampered']:
            self.assertEqual(self.client.post('/app/subscription/checkout', {'token': value, 'offer': 'yes', 'processing': 'yes'}).status_code, 422)

    def test_success_applies_once_even_if_events_arrive_out_of_order(self):
        payment = self.order()
        services.apply(payment.pk, self.data(payment))
        self.sub.refresh_from_db(); until = self.sub.paid_until
        services.apply(payment.pk, self.data(payment))
        payment.refresh_from_db()
        services.apply(payment.pk, self.data(payment, 'canceled'))
        self.sub.refresh_from_db(); payment.refresh_from_db()
        self.assertEqual(self.sub.paid_until, until)
        self.assertTrue(self.sub.is_active)
        self.assertEqual(payment.status, 'succeeded')

    def test_renewal_preserves_remaining_paid_period(self):
        self.sub.status = 'active'; self.sub.paid_until = timezone.now()+timedelta(days=20); self.sub.save()
        previous = self.sub.paid_until
        payment = self.order('year'); services.apply(payment.pk, self.data(payment))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.paid_until, services.add_months(previous, 12))

    def test_calendar_months_handle_january_and_leap_years(self):
        value = datetime(2028, 1, 31, 12, tzinfo=dt_timezone.utc)
        self.assertEqual(services.add_months(value, 1).day, 29)
        self.assertEqual(services.add_months(value.replace(year=2027), 1).day, 28)
        self.assertEqual(services.add_months(value.replace(month=2, day=29), 12).day, 28)

    def test_untrusted_payment_fields_cannot_grant_access(self):
        payment = self.order(); original = self.data(payment)
        changes = [('amount', {'value': '0.01', 'currency': 'RUB'}),
            ('amount', {'value': '199.00', 'currency': 'USD'}), ('recipient', {'account_id': 'other'}),
            ('metadata', {'order_id': str(payment.pk), 'workspace_id': 'other'}),
            ('metadata', {'order_id': 'other', 'workspace_id': str(self.workspace.pk)}),
            ('test', False), ('paid', False)]
        for key, value in changes:
            data = deepcopy(original); data[key] = value
            with self.subTest(key=key,value=value), self.assertRaises(GatewayError):
                services.apply(payment.pk, data)
        self.sub.refresh_from_db(); payment.refresh_from_db()
        self.assertFalse(self.sub.is_active); self.assertIsNone(payment.applied_at)

    def test_webhook_fetches_verified_state_and_recovers_lost_initial_response(self):
        payment = self.order(); data = self.data(payment)
        self.api.side_effect = None; self.api.return_value = data
        body = {'type': 'notification', 'event': 'payment.succeeded',
                'object': {'id': data['id'], 'amount': {'value': '999999.00'}, 'test': False}}
        result = self.client.post('/payments/yookassa/notification', body, content_type='application/json')
        self.assertEqual(result.status_code, 200)
        self.api.assert_called_once_with('GET', 'payments/'+data['id'])
        payment.refresh_from_db(); self.assertEqual(payment.status, 'succeeded')
        self.assertEqual(payment.provider_id, data['id'])

    def test_forged_success_event_does_not_activate_pending_payment(self):
        payment = self.order(); data = self.data(payment, 'pending')
        self.api.side_effect = None; self.api.return_value = data
        result = self.client.post('/payments/yookassa/notification', {'type': 'notification',
            'event': 'payment.succeeded', 'object': {'id': data['id']}}, content_type='application/json')
        self.assertEqual(result.status_code, 200)
        self.sub.refresh_from_db(); self.assertFalse(self.sub.is_active)

    def test_gateway_failure_requests_webhook_redelivery(self):
        self.api.side_effect = GatewayError('temporary')
        self.assertEqual(self.client.post('/payments/yookassa/notification', {'type': 'notification',
            'event': 'payment.succeeded', 'object': {'id': 'provider-example'}}, content_type='application/json').status_code, 503)

    def test_canceled_pending_and_return_page_do_not_activate(self):
        payment = self.order()
        for status in ['pending', 'canceled']:
            services.apply(payment.pk, self.data(payment, status))
        self.assertEqual(self.client.get(f'/app/payments/{payment.pk}?success=true&paid=true').status_code, 200)
        self.sub.refresh_from_db(); self.assertFalse(self.sub.is_active)

    def test_payment_detail_and_status_are_scoped_to_owner(self):
        payment = self.order()
        other = User.objects.create_user('other@example.test')
        workspace = Workspace.objects.create(owner=other); Membership.objects.create(user=other, workspace=workspace)
        self.client.force_login(other)
        for suffix in ['', '/status', '/check']:
            call = self.client.post if suffix == '/check' else self.client.get
            self.assertEqual(call(f'/app/payments/{payment.pk}'+suffix).status_code, 404)

    def test_confirmation_url_cannot_redirect_to_arbitrary_hosts(self):
        for url in ['http://yoomoney.ru/pay', 'https://yoomoney.ru.evil.test', 'https://user@yoomoney.ru', 'https://yoomoney.ru:444/pay']:
            with self.subTest(url=url), self.assertRaises(GatewayError):
                services.safe_confirmation(url)

    def test_working_mode_requires_operator_configuration_and_rejects_test_payments(self):
        with override_settings(YOOKASSA_TEST_MODE=False, LEGAL_LAUNCH_CONFIRMED=False):
            self.assertFalse(services.enabled())
            payment = self.order()
            with self.assertRaises(GatewayError): services.apply(payment.pk, self.data(payment))
        with override_settings(DEBUG=False): self.assertFalse(services.enabled())

    def test_confirmed_refund_is_recorded_for_operator_without_double_extension(self):
        payment = self.order(); data = self.data(payment)
        services.apply(payment.pk, data); self.sub.refresh_from_db(); until=self.sub.paid_until
        data['refunded_amount'] = {'value': '199.00', 'currency': 'RUB'}
        services.apply(payment.pk, data); services.apply(payment.pk, data)
        payment.refresh_from_db(); self.sub.refresh_from_db()
        self.assertEqual(payment.refunded_amount, Decimal('199.00')); self.assertTrue(payment.refund_review)
        self.assertEqual(self.sub.paid_until, until)

    def test_legal_documents_and_signed_consents_are_auditable(self):
        for slug in ['privacy', 'offer', 'processing', 'publication']:
            response = self.client.get('/legal/'+slug)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Дворников Михаил Валериевич')
            self.assertContains(response, '615308640848')
        self.sub.status='active'; self.sub.paid_until=timezone.now()+timedelta(days=1);self.sub.save()
        card=create_card(self.user)
        response=self.client.post(f'/app/cards/{card.pk}/publish', {'draft_version':1,
            'public_consent':'yes','publication_conditions':'<script>Не использовать для рекламы</script>'})
        self.assertEqual(response.status_code,303)
        record=LegalAcceptance.objects.get(document='publication')
        self.assertEqual(record.document_sha256,hashlib.sha256(record.document_text.encode()).hexdigest())
        card.refresh_from_db();self.assertEqual(record.scope['revision'],str(card.published_revision_id))
        page=self.client.get(f'/c/{card.public_id}')
        self.assertContains(page,'&lt;script&gt;Не использовать для рекламы&lt;/script&gt;')
        self.assertNotContains(page,'<script>Не использовать')

    def test_checkout_is_csrf_protected(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post('/app/subscription/checkout', {'token':self.token(),'offer':'yes','processing':'yes'}).status_code,403)
