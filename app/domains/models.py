import uuid
import hashlib
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac


class DomainBinding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=253, unique=True)
    workspace = models.OneToOneField('workspaces.Workspace', on_delete=models.CASCADE)
    root_card = models.ForeignKey('cards.Card', on_delete=models.CASCADE)
    verification_nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    verification_token_hash = models.CharField(max_length=64, editable=False)
    state = models.CharField(max_length=16, choices=[('pending_dns', 'Ожидает DNS'), ('verified', 'DNS подтверждён'),
        ('queued', 'В очереди HTTPS'), ('issuing', 'Выпускается HTTPS'), ('active', 'HTTPS подключён'),
        ('error', 'Ошибка подключения'), ('disabled', 'Отключён')], default='pending_dns')
    blocked = models.BooleanField(default=False)
    generation = models.UUIDField(default=uuid.uuid4, editable=False)
    checked_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    certificate_expires_at = models.DateTimeField(null=True, blank=True)
    requested_at = models.DateTimeField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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


class DomainAudit(models.Model):
    workspace = models.ForeignKey('workspaces.Workspace', on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    hostname = models.CharField(max_length=253)
    action = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)


class DomainWorker(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    heartbeat_at = models.DateTimeField()
