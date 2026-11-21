from django.contrib import admin
from .models import Subscription, Payment
from .forms import PaymentAdminForm
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('workspace', 'status', 'paid_until')
    readonly_fields = ('workspace', 'plan')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['paid_until'].help_text = 'Ручная корректировка после согласованного возврата или исправления. Изменение фиксируется журналом администратора.'
        return form

    def has_add_permission(self, request):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    form = PaymentAdminForm
    list_display = ('id', 'user', 'amount', 'status', 'test', 'refund_review', 'receipt_sent_at')
    list_filter = ('status', 'test', 'refund_review', 'receipt_sent_at')
    search_fields = ('id', 'user__email', 'provider_id')
    readonly_fields = tuple(field.name for field in Payment._meta.fields if field.name not in ['receipt_url', 'refund_review'])
    actions = ['send_np_receipt']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Передать покупателю ссылку на сформированный чек НПД')
    def send_np_receipt(self, request, queryset):
        for payment in queryset:
            if payment.status != 'succeeded' or not payment.receipt_url or payment.test:
                self.message_user(request, f'{payment.pk}: нужен оплаченный рабочий платёж и ссылка чека.', level='warning')
                continue
            try:
                sent = send_mail('Чек за подписку «Визитка»',
                    f'Исполнитель: {settings.OPERATOR_NAME}, ИНН {settings.OPERATOR_INN}.\n'
                    f'Платёж: {payment.pk}, сумма {payment.amount} ₽.\nЧек НПД: {payment.receipt_url}\n'
                    f'Поддержка: {settings.OPERATOR_EMAIL}', settings.DEFAULT_FROM_EMAIL, [payment.user.email])
                if sent:
                    Payment.objects.filter(pk=payment.pk).update(receipt_sent_at=timezone.now())
            except OSError:
                self.message_user(request, f'{payment.pk}: письмо не отправлено; повторите позже.', level='error')
