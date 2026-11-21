from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from urllib.parse import urlsplit

from accounts.views import redirect303
from .models import PhysicalCard
from .physical import PhysicalCardForm, own_physical, physical_url, create_physical, update_physical
from .services import workspace_for, public_card, Conflict
from .views import qr_response


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def index(request):
    workspace = workspace_for(request.user)
    form = PhysicalCardForm(request.POST if request.method == 'POST' else None, workspace=workspace,
                            initial={'card': request.GET.get('card'), 'enabled': True})
    if request.method == 'POST' and form.is_valid():
        try:
            item = create_physical(request.user, form.cleaned_data['label'], form.cleaned_data['card'],
                                   form.cleaned_data['enabled'])
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Ссылка создана. Используйте её и для QR, и для записи в NFC.')
            return redirect303(reverse('physical_edit', args=[item.pk]))
    items = PhysicalCard.objects.filter(workspace=workspace).select_related('card').order_by('-created_at')
    return render(request, 'cards/physical_index.html', {'form': form, 'items': items},
                  status=422 if request.method == 'POST' else 200)


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    item = own_physical(request.user, pk)
    form = PhysicalCardForm(request.POST if request.method == 'POST' else None,
        workspace=item.workspace, initial={'label': item.label, 'card': item.card_id,
                                           'enabled': item.enabled, 'version': item.version})
    status = 200
    if request.method == 'POST':
        status = 422
        if form.is_valid():
            try:
                update_physical(request.user, pk, form.cleaned_data.get('version'),
                    form.cleaned_data['label'], form.cleaned_data['card'], form.cleaned_data['enabled'])
            except Conflict as error:
                form.add_error(None, str(error))
                status = 409
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Привязка обновлена. QR и запись в NFC менять не нужно.')
                return redirect303(reverse('physical_edit', args=[pk]))
    return render(request, 'cards/physical_edit.html', {'form': form, 'item': item,
        'physical_url': physical_url(item),
        'local_only': urlsplit(physical_url(item)).hostname in ('localhost', '127.0.0.1', '::1'),
        'events': item.events.select_related('target_card').order_by('-created_at')[:10]}, status=status)


@login_required
@never_cache
@require_GET
def qr(request, pk):
    return qr_response(physical_url(own_physical(request.user, pk)), filename='physical-card-qr.png')


@never_cache
@require_GET
def resolve(request, public_id):
    item = get_object_or_404(PhysicalCard.objects.select_related('card'), public_id=public_id,
                            enabled=True, blocked=False, card__isnull=False)
    if item.card.workspace_id != item.workspace_id:
        raise Http404
    card = public_card(item.card.public_id, workspace=getattr(request, 'domain_workspace', None))
    response = HttpResponseRedirect(reverse('public', args=[card.public_id]))
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
