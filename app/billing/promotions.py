import re
from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from workspaces.models import Workspace
from .models import AccessGrant, PromoCode, Subscription


def create_grant(workspace, user, days, permanent=False, **extra):
    if not 1 <= days <= 3650:
        raise ValidationError('Укажите от 1 до 3650 дней.')
    subscription, _ = Subscription.objects.get_or_create(workspace=workspace)
    now = timezone.now()
    until = subscription.access_until
    return AccessGrant.objects.create(workspace=workspace, user=user, days=days, permanent=permanent,
        starts_at=now, ends_at=None if permanent else max(now, until or now) + timedelta(days=days), **extra)


@transaction.atomic
def grant_access(actor, user, days=30, permanent=False, note=''):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('billing.add_accessgrant'):
        raise PermissionDenied
    workspace = Workspace.objects.select_for_update().filter(owner=user, membership__user=user).first()
    if not workspace or not user.is_active:
        raise ValidationError('Выберите действующий зарегистрированный аккаунт с кабинетом.')
    return create_grant(workspace, user, days, permanent, issued_by=actor, note=note)


@transaction.atomic
def redeem(user, raw_code):
    if not user.is_active or not user.email_verified_at:
        raise ValidationError('Для активации промокода подтвердите электронную почту.')
    code = raw_code.strip().upper()
    if not re.fullmatch(r'[A-Z0-9_-]{4,40}', code):
        raise ValidationError('Промокод недоступен. Проверьте написание и срок действия.')
    # Same lock order as payments and manual grants; the code lock enforces the global quota.
    workspace = Workspace.objects.select_for_update().get(owner=user, membership__user=user)
    promo = PromoCode.objects.select_for_update().filter(code=code).first()
    now = timezone.now()
    if (not promo or not promo.active or promo.starts_at > now or
            promo.expires_at and promo.expires_at <= now or
            promo.max_uses is not None and promo.uses >= promo.max_uses or
            promo.email and promo.email != user.email.lower()):
        raise ValidationError('Промокод недоступен. Проверьте написание и срок действия.')
    if AccessGrant.objects.filter(promo=promo, user=user).exists():
        raise ValidationError('Вы уже использовали этот промокод.')
    subscription, _ = Subscription.objects.get_or_create(workspace=workspace)
    if subscription.is_permanent:
        raise ValidationError('У вас уже есть бессрочный доступ к Профи.')
    grant = create_grant(workspace, user, promo.days, promo=promo)
    return grant


@transaction.atomic
def revoke_access(actor, pk):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('billing.change_accessgrant'):
        raise PermissionDenied
    scope = AccessGrant.objects.only('workspace_id').get(pk=pk)
    Workspace.objects.select_for_update().get(pk=scope.workspace_id)
    grant = AccessGrant.objects.select_for_update().get(pk=pk)
    if grant.revoked_at:
        return False
    grant.revoked_at, grant.revoked_by = timezone.now(), actor
    grant.save(update_fields=['revoked_at', 'revoked_by'])
    return True
