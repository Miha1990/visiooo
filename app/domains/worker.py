import uuid
import logging
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from cards.services import public_card
from .models import DomainBinding, DomainWorker
from .dns import check_dns, configured
from .services import audit
from . import nginx

logger = logging.getLogger(__name__)


def heartbeat():
    DomainWorker.objects.update_or_create(pk=1, defaults={'heartbeat_at': timezone.now()})


@transaction.atomic
def claim():
    now = timezone.now()
    binding = DomainBinding.objects.select_for_update().filter(blocked=False).filter(
        Q(state='queued') | Q(state='issuing', lease_until__lt=now)).order_by('requested_at').first()
    if not binding:
        return None
    binding.state = 'issuing'
    binding.lease_until = now + timedelta(minutes=10)
    binding.generation = uuid.uuid4()
    binding.save()
    return binding


def still_current(binding):
    return DomainBinding.objects.filter(pk=binding.pk, generation=binding.generation,
                                        state='issuing', blocked=False).exists()


def process_one():
    heartbeat()
    if not configured():
        return
    binding = claim()
    if not binding:
        return
    try:
        public_card(binding.root_card.public_id, workspace=binding.workspace)
        if not check_dns(binding) or not still_current(binding):
            raise RuntimeError('DNS изменился. Подтвердите записи повторно.')
        expires = nginx.provision(binding)
        # Disabling/reassigning during issuance must never activate a stale job.
        if still_current(binding) and check_dns(binding):
            updated = DomainBinding.objects.filter(pk=binding.pk, generation=binding.generation,
                state='issuing', blocked=False).update(state='active', lease_until=None,
                    verified_at=timezone.now(), checked_at=timezone.now(), certificate_expires_at=expires, error='')
            if updated:
                audit(binding, None, 'tls_active')
        elif still_current(binding):
            raise RuntimeError('DNS изменился во время выпуска HTTPS.')
    except Exception:
        logger.exception('Domain certificate job failed for %s', binding.hostname)
        updated = DomainBinding.objects.filter(pk=binding.pk, generation=binding.generation,
            state='issuing').update(state='error', lease_until=None, verified_at=None,
                error='Не удалось подключить HTTPS. Проверьте DNS и обратитесь к администратору сервера.')
        if updated:
            audit(binding, None, 'tls_failed')


def inspect_active(renew=False):
    cutoff = timezone.now() - timedelta(hours=6)
    bindings = DomainBinding.objects.filter(state='active', blocked=False)
    if not renew:
        bindings = bindings.filter(checked_at__lt=cutoff)[:1]
    for binding in bindings:
        try:
            if not check_dns(binding):
                raise RuntimeError('DNS no longer points to ingress')
            expires = nginx.renew(binding) if renew else nginx.certificate_expiry(binding.hostname)
            if expires <= timezone.now():
                raise RuntimeError('Certificate expired')
            DomainBinding.objects.filter(pk=binding.pk, generation=binding.generation, state='active').update(
                checked_at=timezone.now(), verified_at=timezone.now(), certificate_expires_at=expires)
        except Exception:
            logger.exception('Domain inspection failed for %s', binding.hostname)
            updated = DomainBinding.objects.filter(pk=binding.pk, generation=binding.generation, state='active').update(
                state='error', verified_at=None, error='Проверка DNS или HTTPS не пройдена. Подтвердите домен повторно.')
            if updated:
                audit(binding, None, 'inspection_failed')
