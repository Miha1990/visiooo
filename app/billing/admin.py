from django.contrib import admin
from .models import Subscription, Payment, PromoCode, AccessGrant, PaymentNotificationSettings, PaymentNotification
from smtplib import SMTPException
from .forms import PaymentAdminForm, PromoAdminForm, AccessGrantAdminForm
from .promotions import grant_access, revoke_access
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('account', 'status', 'paid_until', 'access_until', 'is_permanent')
    search_fields = ('workspace__owner__email',)
    readonly_fields = ('workspace', 'plan', 'access_until', 'is_permanent')

    @admin.display(description='Аккаунт')
    def account(self, obj):
        return obj.workspace.owner.email

    @admin.display(description='Доступ до')
    def access_until(self, obj):
        return obj.access_until

    @admin.display(description='Бессрочно', boolean=True)
    def is_permanent(self, obj):
        return obj.is_permanent

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['paid_until'].help_text = 'Ручная корректировка после согласованного возврата или исправления. Изменение фиксируется журналом администратора.'
        return form

    def has_add_permission(self, request):
        return False


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    form = PromoAdminForm
    list_display = ('code', 'days', 'active', 'starts_at', 'expires_at', 'max_uses', 'activations', 'email')
    list_filter = ('active',)
    search_fields = ('code', 'email', 'note')
    readonly_fields = ('activations',)

    @admin.display(description='Активаций')
    def activations(self, obj):
        return obj.uses

    def get_readonly_fields(self, request, obj=None):
        return ('activations', 'code') if obj and obj.uses else ('activations',)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    form = AccessGrantAdminForm
    list_display = ('user', 'days', 'permanent', 'starts_at', 'ends_at', 'promo', 'issued_by', 'revoked_at')
    list_filter = ('permanent', 'revoked_at')
    search_fields = ('user__email', 'promo__code', 'note')
    autocomplete_fields = ('user',)
    actions = ('revoke_selected',)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return tuple(field.name for field in AccessGrant._meta.fields)
        return ('workspace', 'starts_at', 'ends_at', 'promo', 'issued_by', 'revoked_at', 'revoked_by')

    def save_model(self, request, obj, form, change):
        if not change:
            grant = grant_access(request.user, obj.user, obj.days, obj.permanent, obj.note)
            obj.__dict__.update(grant.__dict__)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Отозвать выбранные бесплатные доступы', permissions=['change'])
    def revoke_selected(self, request, queryset):
        count = 0
        for pk in queryset.values_list('pk', flat=True):
            if revoke_access(request.user, pk):
                self.log_change(request, AccessGrant.objects.get(pk=pk), 'Бесплатный доступ отозван.')
                count += 1
        self.message_user(request, f'Отозвано бесплатных доступов: {count}. Оплаченные сроки сохранены.')


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
            except (OSError, SMTPException):
                self.message_user(request, f'{payment.pk}: письмо не отправлено; повторите позже.', level='error')


@admin.register(PaymentNotificationSettings)
class PaymentNotificationSettingsAdmin(admin.ModelAdmin):
    fields = ('email',)
    list_display = ('__str__', 'email')
    actions = ('send_test_notification',)

    def has_add_permission(self, request):
        return not PaymentNotificationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Отправить проверочное письмо на указанную почту', permissions=['change'])
    def send_test_notification(self, request, queryset):
        for configuration in queryset:
            if not configuration.email:
                self.message_user(request, 'Сначала сохраните почту для уведомлений.', level='warning')
                continue
            try:
                sent = send_mail('Проверка уведомлений «Визитки»',
                    'Это проверочное письмо. Оплата не проводилась.\n'
                    'На эту почту будут приходить уведомления о подтверждённых оплатах '
                    'с суммой и почтой покупателя для отправки чека НПД.',
                    settings.DEFAULT_FROM_EMAIL, [configuration.email])
                if not sent:
                    raise OSError('Mail was not accepted')
            except (OSError, SMTPException):
                self.message_user(request, 'Не удалось передать письмо почтовому серверу. Проверьте настройки почты.', level='error')
            else:
                self.message_user(request, 'Проверочное письмо передано почтовому серверу. Проверьте входящие и папку нежелательной почты.')


@admin.register(PaymentNotification)
class PaymentNotificationAdmin(admin.ModelAdmin):
    list_display = ('payment', 'customer_email', 'recipient', 'created_at', 'sent_at', 'attempts', 'last_error')
    list_filter = ('sent_at',)
    search_fields = ('payment__id', 'customer_email', 'recipient')
    readonly_fields = tuple(field.name for field in PaymentNotification._meta.fields)
    actions = ('retry_selected',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Повторить отправку неотправленных уведомлений', permissions=['change'])
    def retry_selected(self, request, queryset):
        count = queryset.filter(sent_at__isnull=True).update(retry_at=timezone.now())
        self.message_user(request, f'Поставлено на повторную отправку: {count}.')
