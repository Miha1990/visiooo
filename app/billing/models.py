from django.db import models
from django.utils import timezone
from workspaces.models import Workspace
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.db.models.functions import Lower
from django.db.models import Q, Max, Count
import secrets
import uuid


class Subscription(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    plan = models.CharField(max_length=10, default='pro', editable=False, verbose_name='Тариф', choices=[('pro', 'Профи')])
    status = models.CharField(max_length=10, choices=[('pending', 'Ожидает оплаты'), ('active', 'Активна'),
                                                    ('expired', 'Истекла')], default='pending', verbose_name='Статус оплаты')
    paid_until = models.DateTimeField(null=True, blank=True, verbose_name='Оплачено до')

    @property
    def is_active(self):
        now = timezone.now()
        if self.status == 'active' and self.paid_until and self.paid_until > now:
            return True
        return AccessGrant.objects.filter(workspace_id=self.workspace_id, revoked_at__isnull=True,
            starts_at__lte=now).filter(Q(permanent=True) | Q(ends_at__gt=now)).exists()

    def access_state(self):
        now = timezone.now()
        paid = self.paid_until if self.status == 'active' and self.paid_until and self.paid_until > now else None
        grants = AccessGrant.objects.filter(workspace_id=self.workspace_id, revoked_at__isnull=True,
                                           starts_at__lte=now).filter(Q(permanent=True) | Q(ends_at__gt=now))
        result = grants.aggregate(until=Max('ends_at'), permanent=Count('pk', filter=Q(permanent=True)))
        ends = [value for value in (paid, result['until']) if value]
        return (max(ends) if ends else None, bool(result['permanent']))

    @property
    def access_until(self):
        return self.access_state()[0]

    @property
    def is_permanent(self):
        return self.access_state()[1]

    def __str__(self):
        return f'Подписка — {self.workspace.owner.email}'

    class Meta:
        verbose_name = 'подписка'
        verbose_name_plural = 'Подписки'


def new_promo_code():
    return secrets.token_hex(6).upper()


class PromoCode(models.Model):
    code = models.CharField('Промокод', max_length=40, unique=True, default=new_promo_code,
        validators=[RegexValidator(r'\A[A-Z0-9_-]{4,40}\Z', 'Используйте 4–40 латинских букв, цифр, дефисов или подчёркиваний.')])
    days = models.PositiveSmallIntegerField('Бесплатных дней Профи', default=30,
        validators=[MinValueValidator(1), MaxValueValidator(3650)])
    active = models.BooleanField('Действует', default=True)
    starts_at = models.DateTimeField('Действует с', default=timezone.now)
    expires_at = models.DateTimeField('Действует до', null=True, blank=True)
    max_uses = models.PositiveIntegerField('Лимит активаций', default=1, null=True, blank=True,
        validators=[MinValueValidator(1)], help_text='Пустое значение — без общего лимита. Каждый аккаунт — один раз.')
    email = models.EmailField('Только для почты', blank=True, help_text='Пустое значение — для любых аккаунтов.')
    note = models.CharField('Примечание', max_length=250, blank=True)

    class Meta:
        verbose_name = 'промокод'
        verbose_name_plural = 'Промокоды'
        constraints = [models.UniqueConstraint(Lower('code'), name='promo_code_case_unique'),
            models.CheckConstraint(condition=Q(days__gte=1, days__lte=3650), name='promo_days_valid'),
            models.CheckConstraint(condition=Q(max_uses__isnull=True) | Q(max_uses__gte=1), name='promo_limit_valid')]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    @property
    def uses(self):
        return self.accessgrant_set.count() if self.pk else 0


class AccessGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Аккаунт')
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, verbose_name='Кабинет')
    days = models.PositiveSmallIntegerField('Бесплатных дней', default=30,
        validators=[MinValueValidator(1), MaxValueValidator(3650)])
    permanent = models.BooleanField('Бессрочный доступ', default=False, help_text='Если включено, число дней не учитывается.')
    starts_at = models.DateTimeField('Выдан', default=timezone.now, editable=False)
    ends_at = models.DateTimeField('Доступ до', null=True, blank=True, editable=False)
    promo = models.ForeignKey(PromoCode, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Промокод')
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                 related_name='issued_access_grants', verbose_name='Выдал')
    note = models.CharField('Примечание', max_length=250, blank=True)
    revoked_at = models.DateTimeField('Отозван', null=True, blank=True, editable=False)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='revoked_access_grants', verbose_name='Отозвал')

    class Meta:
        verbose_name = 'бесплатный доступ'
        verbose_name_plural = 'Бесплатные доступы'
        ordering = ['-starts_at']
        constraints = [models.UniqueConstraint(fields=['promo', 'user'], name='promo_once_per_user'),
            models.CheckConstraint(condition=Q(days__gte=1, days__lte=3650), name='grant_days_valid'),
            models.CheckConstraint(condition=Q(permanent=True, ends_at__isnull=True) | Q(permanent=False, ends_at__isnull=False), name='grant_end_valid')]

    def __str__(self):
        return f'{self.user}: ' + ('бессрочно' if self.permanent else f'{self.days} дней')


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, verbose_name='Личный кабинет')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name='Пользователь')
    period = models.CharField(max_length=8, choices=[('month', 'Месяц'), ('year', 'Год')], verbose_name='Срок подписки')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма, ₽')
    status = models.CharField(max_length=20, default='new', choices=[('new', 'Создан'),
        ('pending', 'Ожидает оплаты'), ('succeeded', 'Оплачен'), ('canceled', 'Отменён')], verbose_name='Статус')
    provider_id = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name='Идентификатор в ЮКассе')
    confirmation_url = models.URLField(max_length=2048, blank=True, verbose_name='Ссылка на оплату')
    shop_id = models.CharField(max_length=64, verbose_name='Номер магазина ЮКассы')
    test = models.BooleanField(default=True, verbose_name='Тестовый платёж')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    applied_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата начисления доступа')
    access_start = models.DateTimeField(null=True, blank=True, verbose_name='Начало доступа')
    access_end = models.DateTimeField(null=True, blank=True, verbose_name='Окончание доступа')
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Возвращено, ₽')
    refund_review = models.BooleanField(default=False, verbose_name='Требуется проверка возврата')
    receipt_url = models.URLField(max_length=2048, blank=True, verbose_name='Ссылка на чек НПД')
    receipt_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Чек отправлен')

    class Meta:
        verbose_name = 'платёж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='payment_positive_amount')]

    def __str__(self):
        return f'Платёж {self.pk}'


class PaymentNotificationSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    email = models.EmailField('Почта для уведомлений об оплатах', blank=True,
        help_text='Укажите свою почту. На неё придут сумма оплаты и почта покупателя для отправки чека. Пока поле пустое, уведомления ждут в очереди.')

    class Meta:
        verbose_name = 'настройка уведомлений об оплатах'
        verbose_name_plural = 'Настройки уведомлений об оплатах'
        constraints = [models.CheckConstraint(condition=Q(id=1), name='payment_notification_settings_singleton')]

    def __str__(self):
        return 'Уведомления об оплатах'


class PaymentNotification(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name='operator_notification', verbose_name='Платёж')
    customer_email = models.EmailField('Почта покупателя для чека')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Передано почтовому серверу')
    recipient = models.EmailField('Отправлено на почту', blank=True)
    attempts = models.PositiveIntegerField(default=0, verbose_name='Попыток отправки')
    retry_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Следующая попытка')
    last_error = models.CharField(max_length=80, blank=True, verbose_name='Причина задержки')

    class Meta:
        verbose_name = 'уведомление об оплате'
        verbose_name_plural = 'Уведомления об оплатах'
        ordering = ['-created_at']

    def __str__(self):
        return f'Уведомление о платеже {self.payment_id}'
