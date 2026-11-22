from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from billing.models import Subscription
from workspaces.models import Workspace
from .models import Card, CardRevision
from .validation import validate_content
from .asset_cleanup import schedule_cleanup


class Conflict(Exception):
    pass


def workspace_for(user):
    return get_object_or_404(Workspace, owner=user, membership__user=user, membership__role='owner')


def own_card(user, pk):
    return get_object_or_404(Card.objects.select_related('published_revision'), pk=pk,
                             workspace=workspace_for(user), status__in=['draft', 'published'])


def active_subscription(workspace):
    sub = Subscription.objects.filter(workspace=workspace).first()
    return bool(sub and sub.is_active)


@transaction.atomic
def create_card(user):
    workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    limit = 3 if active_subscription(workspace) else 1
    if workspace.card_set.exclude(status='deleted').count() >= limit:
        raise ValidationError(f'Доступно визиток: {limit}. Для трёх визиток нужен активный Профи.')
    return Card.objects.create(workspace=workspace)


@transaction.atomic
def save_card(user, pk, version, content):
    Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    card = own_card(user, pk)
    validate_content(content, workspace=card.workspace)
    # Conditional UPDATE also protects against stale writes with SQLite.
    changed = Card.objects.filter(pk=card.pk, draft_version=version, status__in=['draft', 'published']).update(
        draft=content, draft_version=version + 1, updated_at=timezone.now())
    if not changed:
        raise Conflict('Визитка изменена в другой вкладке. Скопируйте правки и обновите страницу.')
    schedule_cleanup(card.workspace_id)


@transaction.atomic
def publish_card(user, pk, version, publication_conditions=''):
    workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    card = get_object_or_404(Card.objects.select_for_update(), pk=pk, workspace=workspace,
                            status__in=['draft', 'published'])
    if card.draft_version != version:
        raise Conflict('Перед публикацией обновите страницу: черновик уже изменён.')
    if card.blocked:
        raise ValidationError('Визитка заблокирована администратором.')
    if not user.email_verified_at:
        raise ValidationError('Сначала подтвердите email по ссылке из письма.')
    if not active_subscription(workspace):
        raise ValidationError('Для публикации необходим оплаченный Профи.')
    validate_content(card.draft, workspace=workspace)
    revision = CardRevision.objects.create(card=card, content=card.draft,
                                            publication_conditions=publication_conditions)
    card.published_revision = revision
    card.status = 'published'
    card.save(update_fields=['published_revision', 'status', 'updated_at'])
    schedule_cleanup(workspace.pk)
    return card


@transaction.atomic
def delete_card(user, pk):
    workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    card = own_card(user, pk)
    # Keep the identifier reserved for existing printed QR codes.
    Card.objects.filter(pk=card.pk).update(status='deleted', draft={}, published_revision=None)
    card.revisions.all().delete()
    schedule_cleanup(workspace.pk)


@transaction.atomic
def unpublish_card(user, pk):
    Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    card = own_card(user, pk)
    Card.objects.filter(pk=card.pk).update(status='draft')


def public_card(public_id, workspace=None):
    scope = {'workspace': workspace} if workspace is not None else {}
    card = get_object_or_404(Card.objects.select_related('published_revision', 'workspace'),
                            public_id=public_id, status='published', blocked=False,
                            published_revision__isnull=False, **scope)
    if not active_subscription(card.workspace) or not card.workspace.owner.is_active:
        from django.http import Http404
        raise Http404
    return card
