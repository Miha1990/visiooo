"""Durable operator notifications. SMTP acceptance is not inbox delivery."""
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import PaymentNotification, PaymentNotificationSettings


def send_pending(limit=100):
    configuration = PaymentNotificationSettings.objects.filter(pk=1).first()
    if not configuration or not configuration.email:
        return 0, 0
    sent, failed = 0, 0
    for _ in range(limit):
        with transaction.atomic():
            # A lock prevents two workers from mailing the same row concurrently.
            notice = PaymentNotification.objects.select_for_update(skip_locked=True).filter(
                sent_at__isnull=True, retry_at__lte=timezone.now()).order_by('retry_at', 'pk').first()
            if notice is None:
                break
            payment = notice.payment
            if payment.test or payment.status != 'succeeded' or not payment.applied_at:
                notice.last_error = 'Платёж не подтверждён или тестовый'
                notice.retry_at = timezone.now() + timedelta(hours=1)
                notice.save(update_fields=['last_error', 'retry_at'])
                continue
            notice.attempts += 1
            try:
                if not settings.DEBUG and settings.EMAIL_BACKEND in (
                    'django.core.mail.backends.console.EmailBackend', 'django.core.mail.backends.dummy.EmailBackend'):
                    raise RuntimeError('SMTP is not configured')
                paid_at = timezone.localtime(payment.applied_at).strftime('%d.%m.%Y %H:%M')
                description = 'Доступ к сервису «Визитка Профи» на ' + ('1 календарный месяц' if payment.period == 'month' else '12 календарных месяцев')
                body = (f'Подтверждена оплата подписки «Визитка».\n\n'
                    f'Номер платежа: {payment.pk}\nНомер в ЮКассе: {payment.provider_id}\n'
                    f'Дата подтверждения: {paid_at} (московское время)\n'
                    f'Услуга: {description}\nСумма оплаты покупателя: {payment.amount:.2f} ₽\n'
                    f'Почта покупателя для отправки чека: {notice.customer_email}\n\n'
                    'Сформируйте чек НПД вручную в «Мой налог» и отправьте его покупателю. '
                    'Это письмо не является чеком.\n'
                    f'Возвращено на момент отправки уведомления: {payment.refunded_amount:.2f} ₽. '
                    'При возврате проверьте необходимость корректировки чека.\n\n'
                    f'Платёж в админке: {settings.PUBLIC_BASE_URL}/admin/billing/payment/{payment.pk}/change/\n'
                    'В админке можно сохранить ссылку на готовый чек и отправить её покупателю действием '
                    '«Передать покупателю ссылку на сформированный чек НПД».')
                accepted = send_mail('Получена оплата «Визитки» — нужно сформировать чек НПД',
                    body, settings.DEFAULT_FROM_EMAIL, [configuration.email], fail_silently=False)
                if accepted != 1:
                    raise RuntimeError('Mail was not accepted')
            except Exception as error:
                # Do not store SMTP replies: they may contain credentials or personal data.
                notice.last_error = type(error).__name__
                notice.retry_at = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** min(notice.attempts - 1, 7)))
                failed += 1
            else:
                notice.sent_at = timezone.now()
                notice.recipient = configuration.email
                notice.last_error = ''
                sent += 1
            notice.save()
    return sent, failed
