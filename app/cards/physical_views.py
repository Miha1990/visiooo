from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from urllib.parse import urlsplit

from accounts.views import redirect303
from .models import PhysicalCard
from .physical import (PhysicalCardForm, PhysicalIssueForm, PhysicalActivationForm, own_physical,
                       physical_url, create_physical, update_physical, issue_physical, activate_physical)
from .services import workspace_for, public_card, Conflict
from .views import qr_response


@login_required
@permission_required('cards.add_physicalcard', raise_exception=True)
@never_cache
@require_http_methods(['GET', 'POST'])
def issue(request):
    if not request.user.is_staff:
        raise PermissionDenied
    form = PhysicalIssueForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        issue_physical(request.user, form.cleaned_data['label'], form.cleaned_data['count'])
        messages.success(request, 'Заготовки выпущены. Запишите ссылку каждой карты в NFC и используйте эту же ссылку для её QR.')
        return redirect303(reverse('physical_issue'))
    page = Paginator(PhysicalCard.objects.filter(workspace__isnull=True).order_by('-created_at', 'pk'), 50).get_page(request.GET.get('page'))
    return render(request, 'cards/physical_issue.html', {'form': form, 'page': page,
        'stock': [{'item': item, 'url': physical_url(item)} for item in page]},
        status=422 if request.method == 'POST' else 200)


@login_required
@permission_required('cards.add_physicalcard', raise_exception=True)
@never_cache
@require_GET
def stock_csv(request):
    import csv
    if not request.user.is_staff:
        raise PermissionDenied
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="physical-cards.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Название', 'Ссылка для NFC и QR', 'Доступна для активации'])
    for item in PhysicalCard.objects.filter(workspace__isnull=True).order_by('created_at', 'pk').iterator():
        label = item.label
        if label.lstrip().startswith(('=', '+', '-', '@')):
            label = "'" + label
        writer.writerow([label, physical_url(item), 'Да' if item.enabled and not item.blocked else 'Нет'])
    return response


@login_required
@permission_required('cards.add_physicalcard', raise_exception=True)
@never_cache
@require_GET
def stock_qr(request, pk):
    if not request.user.is_staff:
        raise PermissionDenied
    item = get_object_or_404(PhysicalCard, pk=pk, workspace__isnull=True)
    return qr_response(physical_url(item), filename='physical-card-qr.png')


@never_cache
@require_http_methods(['GET', 'POST'])
def activate(request, public_id):
    item = get_object_or_404(PhysicalCard, public_id=public_id, blocked=False, enabled=True)
    if item.workspace_id is not None:
        if request.user.is_authenticated and item.workspace_id == workspace_for(request.user).pk:
            return redirect303(reverse('physical_edit', args=[item.pk]))
        return render(request, 'cards/physical_activate.html', {'already_activated': True}, status=409)
    path = reverse('physical_activate', args=[item.public_id])
    if not request.user.is_authenticated:
        if request.method == 'POST':
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(path)
        request.session['physical_activation'] = item.public_id
        return render(request, 'cards/physical_activate.html', {'activation_path': path})
    workspace = workspace_for(request.user)
    form = PhysicalActivationForm(request.POST if request.method == 'POST' else None, workspace=workspace)
    status = 200
    if request.method == 'POST':
        status = 422
        if form.is_valid():
            try:
                item = activate_physical(request.user, public_id, form.cleaned_data['card'])
            except Conflict as error:
                form.add_error(None, str(error))
                status = 409
            except ValidationError as error:
                form.add_error(None, error)
            else:
                request.session.pop('physical_activation', None)
                messages.success(request, 'Карта активирована. QR и NFC теперь связаны с вашей визиткой. Для посетителей опубликуйте визитку.')
                return redirect303(reverse('physical_edit', args=[item.pk]))
    return render(request, 'cards/physical_activate.html', {'form': form,
        'has_cards': form.fields['card'].queryset.exists(), 'activation_path': path}, status=status)


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
    return render(request, 'cards/physical_index.html', {'form': form, 'items': items,
                  'local_only': urlsplit(settings.PUBLIC_BASE_URL).hostname in ('localhost', '127.0.0.1', '::1')},
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
                            enabled=True, blocked=False)
    if item.workspace_id is None:
        if getattr(request, 'domain_workspace', None) is not None:
            raise Http404
        return HttpResponseRedirect(settings.PUBLIC_BASE_URL.rstrip('/') + reverse('physical_activate', args=[item.public_id]))
    if item.card is None:
        raise Http404
    if item.card.workspace_id != item.workspace_id:
        raise Http404
    card = public_card(item.card.public_id, workspace=getattr(request, 'domain_workspace', None))
    response = HttpResponseRedirect(reverse('public', args=[card.public_id]))
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response
