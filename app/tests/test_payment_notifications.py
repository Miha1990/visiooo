from datetime import timedelta
from decimal import Decimal
from smtplib import SMTPException
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.core import mail
from django.test import TestCase, TransactionTestCase, override_settings
from django.db import connection, connections, close_old_connections
from django.utils import timezone

from accounts.models import User
from billing.models import Payment, PaymentNotification, PaymentNotificationSettings, Subscription
from billing.notifications import send_pending
from billing.services import apply
from billing.gateway import GatewayError
from workspaces.models import Workspace


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEBUG=True, PUBLIC_BASE_URL='https://visiooo.ru', YOOKASSA_SHOP_ID='real-shop', YOOKASSA_TEST_MODE=False)
class PaymentNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('customer@example.test')
        self.workspace = Workspace.objects.create(owner=self.user)
        Subscription.objects.create(workspace=self.workspace)
        self.config, _ = PaymentNotificationSettings.objects.update_or_create(pk=1, defaults={'email': 'owner@example.test'})
        self.payment = Payment.objects.create(workspace=self.workspace, user=self.user, amount=Decimal('199.00'),
            period='month', shop_id='real-shop', test=False)

    def data(self, **kwargs):
        return {'id': 'real-payment', 'status': 'succeeded', 'paid': True, 'test': False,
            'amount': {'value': '199.00', 'currency': 'RUB'}, 'recipient': {'account_id': 'real-shop'},
            'metadata': {'order_id': str(self.payment.pk), 'workspace_id': str(self.workspace.pk)}, **kwargs}

    def test_verified_payment_enqueues_once_and_mail_has_receipt_destination(self):
        apply(self.payment.pk, self.data())
        apply(self.payment.pk, self.data())
        self.assertEqual(PaymentNotification.objects.count(), 1)
        self.assertEqual(send_pending(), (1, 0))
        self.assertEqual(send_pending(), (0, 0))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['owner@example.test'])
        self.assertIn('customer@example.test', message.body)
        self.assertIn('199.00', message.body)
        self.assertIn(str(self.payment.pk), message.body)
        self.assertIn('/admin/billing/payment/', message.body)
        notice = PaymentNotification.objects.get()
        self.assertIsNotNone(notice.sent_at)
        self.payment.refresh_from_db()
        self.assertIsNone(self.payment.receipt_sent_at)

    def test_mail_failure_keeps_payment_active_and_retries(self):
        apply(self.payment.pk, self.data())
        with patch('billing.notifications.send_mail', side_effect=SMTPException('private transport details')):
            self.assertEqual(send_pending(), (0, 1))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'succeeded')
        self.assertTrue(Subscription.objects.get(workspace=self.workspace).is_active)
        notice = PaymentNotification.objects.get()
        self.assertIsNone(notice.sent_at)
        self.assertEqual(notice.last_error, 'SMTPException')
        self.assertGreater(notice.retry_at, timezone.now())
        self.assertEqual(send_pending(), (0, 0))
        PaymentNotification.objects.update(retry_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(send_pending(), (1, 0))

    def test_missing_destination_waits_then_uses_email_from_admin_settings(self):
        self.config.email = ''; self.config.save()
        apply(self.payment.pk, self.data())
        self.assertEqual(send_pending(), (0, 0))
        self.config.email = 'new-owner@example.test'; self.config.save()
        self.assertEqual(send_pending(), (1, 0))
        self.assertEqual(mail.outbox[-1].to, ['new-owner@example.test'])

    def test_failed_validation_cancellation_and_test_payments_never_notify(self):
        invalid = self.data(amount={'value': '1.00', 'currency': 'RUB'})
        with self.assertRaises(GatewayError):
            apply(self.payment.pk, invalid)
        apply(self.payment.pk, self.data(status='canceled', paid=False))
        self.assertFalse(PaymentNotification.objects.exists())
        self.payment.test = True; self.payment.save()
        with override_settings(YOOKASSA_TEST_MODE=True):
            apply(self.payment.pk, self.data(test=True))
        self.assertFalse(PaymentNotification.objects.exists())

    def test_customer_email_snapshot_is_preserved_if_account_email_changes(self):
        apply(self.payment.pk, self.data())
        self.user.email = 'changed@example.test'; self.user.save()
        send_pending()
        self.assertIn('customer@example.test', mail.outbox[-1].body)
        self.assertNotIn('changed@example.test', mail.outbox[-1].body)

    def test_payment_rollback_does_not_leave_notification(self):
        from django.db import transaction
        try:
            with transaction.atomic():
                apply(self.payment.pk, self.data())
                raise RuntimeError('rollback')
        except RuntimeError:
            pass
        self.assertFalse(PaymentNotification.objects.exists())

    def test_rechecking_old_paid_order_does_not_email_historical_sales(self):
        self.payment.applied_at = timezone.now(); self.payment.status = 'succeeded'; self.payment.save()
        apply(self.payment.pk, self.data())
        self.assertFalse(PaymentNotification.objects.exists())

    @override_settings(DEBUG=False, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_is_not_counted_as_production_mail_delivery(self):
        apply(self.payment.pk, self.data())
        self.assertEqual(send_pending(), (0, 1))
        self.assertIsNone(PaymentNotification.objects.get().sent_at)

    @override_settings(ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False)
    def test_admin_can_set_address_and_send_a_test_without_charging(self):
        admin = User.objects.create_superuser('admin@example.test', 'Strong-Test-283!')
        self.client.force_login(admin)
        response = self.client.post('/admin/billing/paymentnotificationsettings/1/change/',
            {'email': 'notifications@example.test', '_save': 'Сохранить'})
        self.assertEqual(response.status_code, 302)
        self.config.refresh_from_db()
        self.assertEqual(self.config.email, 'notifications@example.test')
        response = self.client.post('/admin/billing/paymentnotificationsettings/',
            {'action': 'send_test_notification', '_selected_action': '1'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox[-1].to, ['notifications@example.test'])
        self.assertIn('Оплата не проводилась', mail.outbox[-1].body)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentNotification.objects.count(), 0)


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
@override_settings(DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ConcurrentPaymentNotificationTests(TransactionTestCase):
    def test_parallel_workers_do_not_send_the_same_notification(self):
        user = User.objects.create_user('parallel-buyer@example.test')
        workspace = Workspace.objects.create(owner=user)
        payment = Payment.objects.create(workspace=workspace, user=user, amount=Decimal('199.00'),
            period='month', shop_id='shop', test=False, status='succeeded', applied_at=timezone.now())
        PaymentNotificationSettings.objects.update_or_create(pk=1, defaults={'email': 'owner@example.test'})
        PaymentNotification.objects.create(payment=payment, customer_email=user.email)
        entered, release = Event(), Event()

        def smtp(*args, **kwargs):
            entered.set()
            if not release.wait(10):
                raise RuntimeError('test timeout')
            return 1

        def first_worker():
            close_old_connections()
            try:
                return send_pending()
            finally:
                connections.close_all()

        with patch('billing.notifications.send_mail', side_effect=smtp) as mocked:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(first_worker)
                try:
                    self.assertTrue(entered.wait(10))
                    self.assertEqual(send_pending(), (0, 0))
                finally:
                    release.set()
                self.assertEqual(future.result(timeout=10), (1, 0))
            self.assertEqual(mocked.call_count, 1)
