import calendar
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from workspaces.models import Workspace
from .models import Payment, Subscription, PaymentNotification
from . import gateway

PRICES = {'month': Decimal('199.00'), 'year': Decimal('1490.00')}


def enabled():
    basic = settings.YOOKASSA_ENABLED and settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY
    if settings.YOOKASSA_TEST_MODE:
        return bool(basic and settings.DEBUG)
    return bool(basic and settings.LEGAL_LAUNCH_CONFIRMED and settings.OPERATOR_INN
                and settings.OPERATOR_ADDRESS and settings.DATA_HOSTING_PROVIDER
                and settings.DATA_MAIL_PROVIDER and settings.NPD_RECEIPTS_CONFIRMED
                and urlsplit(settings.PUBLIC_BASE_URL).scheme == 'https')


def add_months(value, months):
    month_index = value.year * 12 + value.month - 1 + months
    year, month = divmod(month_index, 12)
    return value.replace(year=year, month=month + 1,
                         day=min(value.day, calendar.monthrange(year, month + 1)[1]))


def validate(payment, data):
    try:
        checks = [bool(re.fullmatch(r'[a-zA-Z0-9-]{1,64}', data['id'])),
            not payment.provider_id or data['id'] == payment.provider_id,
            data['metadata']['order_id'] == str(payment.pk),
            data['metadata']['workspace_id'] == str(payment.workspace_id),
            data['recipient']['account_id'] == payment.shop_id == settings.YOOKASSA_SHOP_ID,
            data['amount']['currency'] == 'RUB', Decimal(data['amount']['value']) == payment.amount,
            data['test'] is payment.test is settings.YOOKASSA_TEST_MODE,
            data['status'] in ['pending', 'waiting_for_capture', 'succeeded', 'canceled'],
            data['status'] != 'succeeded' or data.get('paid') is True]
        if not all(checks):
            raise ValueError
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise gateway.GatewayError('Платёж не прошёл проверку. Обратитесь в поддержку.') from None


def safe_confirmation(url):
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme == 'https' and parsed.hostname in ['yoomoney.ru', 'yookassa.ru'] and not parsed.username and not parsed.password and parsed.port in (None, 443)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise gateway.GatewayError('Некорректный адрес оплаты. Обратитесь в поддержку.')
    return url


@transaction.atomic
def apply(payment_id, data):
    # The workspace lock serializes different payments extending the same subscription.
    scope = Payment.objects.only('workspace_id').get(pk=payment_id)
    Workspace.objects.select_for_update().get(pk=scope.workspace_id)
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    validate(payment, data)
    payment.provider_id = data['id']
    status = data['status']
    first_success = status == 'succeeded' and payment.applied_at is None
    if status == 'succeeded':
        if payment.applied_at is None:
            sub, _ = Subscription.objects.get_or_create(workspace_id=payment.workspace_id)
            now = timezone.now()
            access_until = sub.access_until
            start = max(now, access_until) if access_until else now
            end = add_months(start, 1 if payment.period == 'month' else 12)
            sub.status, sub.paid_until = 'active', end
            sub.save(update_fields=['status', 'paid_until'])
            payment.applied_at, payment.access_start, payment.access_end = now, start, end
        payment.status = 'succeeded'
        try:
            refund = Decimal(data.get('refunded_amount', {}).get('value', '0'))
            if not refund.is_finite() or not 0 <= refund <= payment.amount:
                raise ValueError
            if refund > payment.refunded_amount:
                payment.refunded_amount = refund
                payment.refund_review = True
        except (InvalidOperation, ValueError, TypeError):
            raise gateway.GatewayError('Не удалось проверить возврат платежа.') from None
    elif payment.applied_at is None:
        payment.status = 'canceled' if status == 'canceled' else 'pending'
    confirmation = (data.get('confirmation') or {}).get('confirmation_url')
    if confirmation:
        payment.confirmation_url = safe_confirmation(confirmation)
    payment.save()
    if first_success and not payment.test:
        PaymentNotification.objects.get_or_create(payment=payment,
            defaults={'customer_email': payment.user.email})
    return payment


def create_or_resume(payment):
    if payment.provider_id:
        return refresh(payment)
    if timezone.now() - payment.created_at >= timedelta(hours=23):
        raise gateway.GatewayError('Срок попытки оплаты истёк. Создайте новый платёж.')
    data = gateway.request('POST', 'payments', {
        'amount': {'value': str(payment.amount), 'currency': 'RUB'}, 'capture': True,
        'confirmation': {'type': 'redirect', 'return_url': f'{settings.PUBLIC_BASE_URL}/app/payments/{payment.pk}'},
        'description': 'Визитка — подписка на ' + ('месяц' if payment.period == 'month' else 'год'),
        'metadata': {'order_id': str(payment.pk), 'workspace_id': str(payment.workspace_id)},
    }, key=payment.pk)
    return apply(payment.pk, data)


def refresh(payment):
    if not payment.provider_id or not re.fullmatch(r'[a-zA-Z0-9-]{1,64}', payment.provider_id):
        raise gateway.GatewayError('Платёж ещё не создан в ЮКассе.')
    return apply(payment.pk, gateway.request('GET', 'payments/' + payment.provider_id))
