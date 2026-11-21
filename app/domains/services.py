import uuid
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from cards.services import workspace_for, own_card, public_card
from workspaces.models import Workspace
from .models import DomainBinding, DomainAudit, DomainWorker
from .validation import normalize_hostname, platform_conflict
from .dns import check_dns, configured


def audit(binding, actor, action):
    DomainAudit.objects.create(workspace=binding.workspace, actor=actor, hostname=binding.hostname, action=action)


def owned(user, pk):
    return get_object_or_404(DomainBinding, pk=pk, workspace=workspace_for(user))


def worker_ready():
    return DomainWorker.objects.filter(pk=1, heartbeat_at__gt=timezone.now() - timedelta(minutes=10)).exists()


@transaction.atomic
def change_target(user, pk, card, generation):
    binding = DomainBinding.objects.select_for_update().get(pk=owned(user, pk).pk)
    if binding.blocked:
        raise ValidationError('Домен заблокирован администратором.')
    if binding.generation != generation:
        raise ValidationError('Настройки изменились в другой вкладке. Обновите страницу.')
    binding.root_card = own_card(user, card.pk)
    binding.generation = uuid.uuid4()
    if binding.state in ('queued', 'issuing'):
        binding.state = 'verified'
        binding.lease_until = None
    binding.save()
    audit(binding, user, 'target_changed')


@transaction.atomic
def add_domain(user, hostname, card):
    workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    card = own_card(user, card.pk)
    hostname = normalize_hostname(hostname)
    if platform_conflict(hostname):
        raise ValidationError('Домен платформы нельзя подключить к визитке.')
    if DomainBinding.objects.filter(workspace=workspace).exists():
        raise ValidationError('Доступен один свой домен. Сначала отключите и удалите прежнюю привязку.')
    try:
        with transaction.atomic():
            binding = DomainBinding.objects.create(workspace=workspace, root_card=card, hostname=hostname)
    except IntegrityError as error:
        raise ValidationError('Этот домен уже добавлен. Отключите его в прежнем аккаунте.') from error
    audit(binding, user, 'added')
    return binding


def verify_domain(user, pk):
    binding = owned(user, pk)
    if binding.blocked:
        raise ValidationError('Домен заблокирован администратором.')
    if not configured():
        raise ValidationError('Администратор ещё не настроил публичный IP сервиса и приём доменов.')
    if binding.checked_at and binding.checked_at > timezone.now() - timedelta(seconds=30):
        raise ValidationError('Повторите проверку DNS через 30 секунд.')
    valid = check_dns(binding)
    with transaction.atomic():
        current = DomainBinding.objects.select_for_update().get(pk=binding.pk)
        if current.generation != binding.generation or current.blocked:
            raise ValidationError('Настройки изменились. Обновите страницу.')
        now = timezone.now()
        current.checked_at = now
        current.verified_at = now if valid else None
        current.error = '' if valid else 'Проверьте TXT и A, удалите конфликтующие A/AAAA. Дождитесь обновления DNS.'
        current.generation = uuid.uuid4()
        current.lease_until = None
        current.state = ('active' if binding.routable else 'verified') if valid else 'pending_dns'
        current.save()
        audit(current, user, 'dns_verified' if valid else 'dns_failed')
    return valid


@transaction.atomic
def request_certificate(user, pk):
    binding = DomainBinding.objects.select_for_update().get(pk=owned(user, pk).pk)
    if binding.blocked or not configured() or not binding.verified_at or binding.verified_at < timezone.now() - timedelta(days=2):
        raise ValidationError('Сначала подтвердите DNS домена.')
    if binding.state in ('queued', 'issuing'):
        raise ValidationError('Сертификат уже ожидает обработки.')
    if not worker_ready():
        raise ValidationError('Сервис выпуска HTTPS пока не запущен администратором.')
    if binding.requested_at and binding.requested_at > timezone.now() - timedelta(minutes=15):
        raise ValidationError('Повторный выпуск доступен через 15 минут.')
    # A paid, published card is required before a domain can become publicly live.
    public_card(binding.root_card.public_id, workspace=binding.workspace)
    binding.state = 'queued'
    binding.error = ''
    binding.requested_at = timezone.now()
    binding.generation = uuid.uuid4()
    binding.save()
    audit(binding, user, 'tls_requested')


@transaction.atomic
def disable_domain(user, pk):
    binding = DomainBinding.objects.select_for_update().get(pk=owned(user, pk).pk)
    if binding.blocked:
        raise ValidationError('Домен заблокирован администратором.')
    binding.state = 'disabled'
    binding.generation = uuid.uuid4()
    binding.verified_at = None
    binding.verification_nonce = uuid.uuid4()
    binding.lease_until = None
    binding.save()
    audit(binding, user, 'disabled')


@transaction.atomic
def remove_domain(user, pk):
    binding = DomainBinding.objects.select_for_update().get(pk=owned(user, pk).pk)
    if binding.blocked:
        raise ValidationError('Домен заблокирован администратором.')
    if binding.state != 'disabled':
        raise ValidationError('Сначала отключите домен.')
    audit(binding, user, 'removed')
    binding.delete()
