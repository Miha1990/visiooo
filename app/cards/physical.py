from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from workspaces.models import Workspace
from .models import Card, PhysicalCard, PhysicalCardEvent
from .services import workspace_for, own_card, Conflict


def physical_url(physical):
    return f'{settings.PUBLIC_BASE_URL}/p/{physical.public_id}'


class PhysicalCardForm(forms.Form):
    label = forms.CharField(label='Название физической визитки', max_length=100,
                            widget=forms.TextInput(attrs={'placeholder': 'Например, моя NFC-визитка'}))
    card = forms.ModelChoiceField(label='Электронная визитка', queryset=Card.objects.none(), required=False,
                                 empty_label='Без привязки — ссылка отключена')
    enabled = forms.BooleanField(label='Включить карточку', required=False, initial=True)
    version = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['card'].queryset = Card.objects.filter(workspace=workspace).exclude(status='deleted')


def own_physical(user, pk):
    return get_object_or_404(PhysicalCard, pk=pk, workspace=workspace_for(user))


@transaction.atomic
def create_physical(user, label, card=None, enabled=True):
    workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    if PhysicalCard.objects.filter(workspace=workspace).count() >= 20:
        raise ValidationError('В пространстве доступно до 20 физических визиток.')
    if card:
        card = own_card(user, card.pk)
    item = PhysicalCard.objects.create(workspace=workspace, card=card, label=label, enabled=enabled)
    PhysicalCardEvent.objects.create(physical_card=item, actor=user, action='created', target_card=card)
    return item


@transaction.atomic
def update_physical(user, pk, version, label, card=None, enabled=True):
    workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
    item = get_object_or_404(PhysicalCard.objects.select_for_update(), pk=pk, workspace=workspace)
    if item.version != version:
        raise Conflict('Привязка уже изменена в другой вкладке. Обновите страницу.')
    if item.blocked:
        raise ValidationError('Физическая визитка заблокирована администратором.')
    if card:
        card = own_card(user, card.pk)
    item.label, item.card, item.enabled = label, card, enabled
    item.version += 1
    item.save(update_fields=['label', 'card', 'enabled', 'version', 'updated_at'])
    PhysicalCardEvent.objects.create(physical_card=item, actor=user,
        action='bound' if card and enabled else 'disabled', target_card=card)
    return item
