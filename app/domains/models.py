import uuid
import hashlib
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac


class DomainBinding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    hostname = models.CharField(max_length=253, unique=True, verbose_name='Домен')
    workspace = models.OneToOneField('workspaces.Workspace', on_delete=models.CASCADE, verbose_name='Личный кабинет')
    root_card = models.ForeignKey('cards.Card', on_delete=models.CASCADE, verbose_name='Визитка')
    verification_nonce = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='Идентификатор проверки')
    verification_token_hash = models.CharField(max_length=64, editable=False, verbose_name='Контрольная сумма подтверждения')
    state = models.CharField(max_length=16, choices=[('pending_dns', 'Ожидает DNS'), ('verified', 'DNS подтверждён'),
        ('queued', 'В очереди HTTPS'), ('issuing', 'Выпускается HTTPS'), ('active', 'HTTPS подключён'),
        ('error', 'Ошибка подключения'), ('disabled', 'Отключён')], default='pending_dns', verbose_name='Состояние')
    blocked = models.BooleanField(default=False, verbose_name='Заблокирован')
    generation = models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='Версия подключения')
    checked_at = models.DateTimeField(null=True, blank=True, verbose_name='Последняя проверка')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Домен подтверждён')
    certificate_expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Сертификат действует до')
    requested_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата запроса сертификата')
    lease_until = models.DateTimeField(null=True, blank=True, verbose_name='Обработка до')
    error = models.CharField(max_length=300, blank=True, verbose_name='Ошибка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    @property
    def verification_token(self):
        return 'myqr-' + salted_hmac('domain-dns', f'{self.pk}:{self.verification_nonce}', algorithm='sha256').hexdigest()

    def save(self, *args, **kwargs):
        self.verification_token_hash = hashlib.sha256(self.verification_token.encode()).hexdigest()
        super().save(*args, **kwargs)

    @property
    def routable(self):
        now = timezone.now()
        return bool(settings.CUSTOM_DOMAINS_ENABLED and not self.blocked and self.state == 'active'
            and self.verified_at and self.verified_at > now - timedelta(days=2)
            and self.certificate_expires_at and self.certificate_expires_at > now
            and self.root_card.workspace_id == self.workspace_id)

    class Meta:
        verbose_name = 'подключение домена'
        verbose_name_plural = 'Подключения доменов'

    def __str__(self):
        return self.hostname


class DomainAudit(models.Model):
    workspace = models.ForeignKey('workspaces.Workspace', on_delete=models.CASCADE, verbose_name='Личный кабинет')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, verbose_name='Пользователь')
    hostname = models.CharField(max_length=253, verbose_name='Домен')
    action = models.CharField(max_length=30, verbose_name='Действие', choices=[
        ('target_changed', 'Изменена визитка'), ('added', 'Домен добавлен'),
        ('dns_verified', 'Домен подтверждён'), ('dns_failed', 'Домен не подтверждён'),
        ('tls_requested', 'Запрошен сертификат'), ('disabled', 'Подключение отключено'),
        ('removed', 'Привязка удалена'), ('tls_active', 'Защищённое соединение подключено'),
        ('tls_failed', 'Ошибка выпуска сертификата'), ('inspection_failed', 'Проверка не пройдена'),
        ('admin_block', 'Заблокирован администратором'), ('admin_unblock', 'Разблокирован администратором')])
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата события')

    class Meta:
        verbose_name = 'событие домена'
        verbose_name_plural = 'События доменов'

    def __str__(self):
        return f'{self.hostname} — {self.get_action_display()}'


class DomainWorker(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    heartbeat_at = models.DateTimeField(verbose_name='Последняя активность')

    class Meta:
        verbose_name = 'обработчик доменов'
        verbose_name_plural = 'Обработчики доменов'
