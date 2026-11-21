from django.db import models
from django.utils import timezone
from workspaces.models import Workspace
from django.conf import settings
import uuid


class Subscription(models.Model):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE)
    plan = models.CharField(max_length=10, default='pro', editable=False)
    status = models.CharField(max_length=10, choices=[('pending', 'Ожидает оплаты'), ('active', 'Активна'),
                                                    ('expired', 'Истекла')], default='pending')
    paid_until = models.DateTimeField(null=True, blank=True)

    @property
    def is_active(self):
        return self.status == 'active' and self.paid_until is not None and self.paid_until > timezone.now()


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    period = models.CharField(max_length=8, choices=[('month', 'Месяц'), ('year', 'Год')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='new', choices=[('new', 'Создан'),
        ('pending', 'Ожидает оплаты'), ('succeeded', 'Оплачен'), ('canceled', 'Отменён')])
    provider_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    confirmation_url = models.URLField(max_length=2048, blank=True)
    shop_id = models.CharField(max_length=64)
    test = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    access_start = models.DateTimeField(null=True, blank=True)
    access_end = models.DateTimeField(null=True, blank=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refund_review = models.BooleanField(default=False)
    receipt_url = models.URLField(max_length=2048, blank=True)
    receipt_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='payment_positive_amount')]
