from io import BytesIO
import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from accounts.views import redirect303
from .forms import CardForm, AvatarUploadForm
from .models import Card
from .image_slots import IMAGE_FIELDS
from .services import (workspace_for, own_card, active_subscription, create_card, save_card,
                       publish_card, public_card, delete_card, unpublish_card, Conflict)
from .vcard import render_vcard
from .blocks import carousel_limit
from .button_builder import BUTTON_TYPES


def public_url(card):
    return f'{settings.PUBLIC_BASE_URL}/c/{card.public_id}'


def qr_response(url, filename='card-qr.png'):
    output = BytesIO()
    qrcode.make(url, error_correction=qrcode.constants.ERROR_CORRECT_M, border=4).save(output, format='PNG')
    response = HttpResponse(output.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@require_GET
def home(request):
    from .examples import example_cards
    return render(request, 'home.html', {'examples': example_cards()})


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def dashboard(request):
    workspace = workspace_for(request.user)
    if request.method == 'POST':
        try:
            card = create_card(request.user)
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
        else:
            return redirect303(f'/app/cards/{card.pk}/edit')
        return redirect303('/app/cards')
    cards = list(Card.objects.filter(workspace=workspace).exclude(status='deleted').select_related('published_revision').order_by('-updated_at'))
    selected = next((card for card in cards if str(card.pk) == request.GET.get('card')), cards[0] if cards else None)
    return render(request, 'cards/dashboard.html', {'cards': cards, 'card': selected,
        'content': selected.draft if selected else {}, 'preview': True,
        'public_url': public_url(selected) if selected else '',
        'subscription': workspace.subscription, 'active_pro': active_subscription(workspace)})


@login_required
@never_cache
@require_GET
def client_menu(request):
    return render(request, 'cards/client_menu.html')


@login_required
@never_cache
@require_GET
def client_analytics(request):
    from .analytics import report
    from django.shortcuts import get_object_or_404
    from django.http import Http404
    workspace = workspace_for(request.user)
    cards = Card.objects.filter(workspace=workspace).exclude(status='deleted')
    selected = None
    if request.GET.get('card'):
        try:
            selected = get_object_or_404(cards, pk=request.GET['card'])
        except (ValueError, ValidationError):
            raise Http404
    counted = cards.filter(pk=selected.pk) if selected else cards
    return render(request, 'cards/client_analytics.html', {
        **report(counted, request.GET.get('period', 'day')), 'cards': cards, 'selected_card': selected,
        'card_count': cards.count(), 'published_count': cards.filter(status='published', blocked=False).count(),
        'draft_count': cards.filter(status='draft').count(), 'active_pro': active_subscription(workspace)})


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    card = own_card(request.user, pk)
    form = CardForm.for_card(card, request.POST if request.method == 'POST' else None)
    status = 200
    if request.method == 'POST':
        status = 422
        if form.is_valid():
            try:
                save_card(request.user, pk, form.cleaned_data['draft_version'], form.content,
                          address=form.cleaned_data['card_address'], address_confirmed=form.cleaned_data['address_confirmed'])
            except Conflict as error:
                form.add_error(None, str(error))
                status = 409
            except ValidationError as error:
                form.add_error('card_address', error)
            else:
                if request.headers.get('Accept') == 'application/json':
                    updated = own_card(request.user,pk)
                    return JsonResponse({'version':updated.draft_version, 'address':updated.public_id, 'public_url':public_url(updated)})
                messages.success(request, 'Черновик сохранён. Для обновления публичной страницы нажмите «Опубликовать».')
                if request.POST.get('save_and_close') == 'yes':
                    return redirect303(f'/app/cards?card={pk}')
                return redirect303(f'/app/cards/{pk}/edit')
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'errors':form.errors.get_json_data(), 'error':'Проверьте поля визитки. Правки не сохранены.'},status=status)
    image_panels = []
    descriptions = {
        'logo': ('Лого', 'Отдельный логотип в левой части обложки.'),
        'background': ('Фон', 'Фотография на фоне всей визитки. Текст останется на светлой подложке.'),
        'avatar': ('Фото', 'Ваш портрет или логотип в круглом блоке профиля.'),
        'header': ('Шапка', 'Отдельная фотография в верхней части визитки.'),
    }
    for target, field in IMAGE_FIELDS.items():
        if target == 'background':
            continue
        if target != 'background' and ('avatar' if target == 'avatar' else 'cover') not in form.blocks:
            continue
        label, description = descriptions[target]
        image_panels.append({'target': target, 'label': label, 'description': description,
            'asset_id': card.draft.get(field),
            'form': AvatarUploadForm(auto_id=f'{target}_%s', initial={
                'card_id': card.pk, 'draft_version': card.draft_version, 'target': target})})
    return render(request, 'cards/edit.html', {'card': card, 'form': form, 'content': card.draft,
        'initial_view': 'preview' if request.GET.get('view') == 'preview' else 'edit',
        'builder_options': BUTTON_TYPES,
        'image_panels': image_panels, 'content_blocks':form.blocks,
        'gallery_ids':card.draft.get('galleryAssetIds', []),
        'gallery_limit':carousel_limit(),
        'public_url': public_url(card), 'active_pro': active_subscription(card.workspace)}, status=status)


@login_required
@never_cache
@require_http_methods(['GET'])
def address_available(request, pk):
    from .addresses import clean_address
    card = own_card(request.user, pk)
    try:
        value = clean_address(request.GET.get('address', ''), card)
    except ValidationError as error:
        return JsonResponse({'available':False, 'message':' '.join(error.messages)})
    return JsonResponse({'available':True, 'address':value, 'message':'Адрес доступен.' if value != card.public_id else 'Текущий адрес визитки.'})


@login_required
@require_POST
def publish(request, pk):
    own_card(request.user, pk)
    if request.POST.get('public_consent') != 'yes':
        return HttpResponse('Подтвердите, что контакты станут публичными.', status=422)
    try:
        version = int(request.POST.get('draft_version', '0'))
    except ValueError:
        return HttpResponse('Некорректная версия черновика.', status=422)
    try:
        conditions = request.POST.get('publication_conditions', '').strip()
        if len(conditions) > 2000:
            return HttpResponse('Условия публикации: не более 2000 символов.', status=422)
        from django.db import transaction
        from accounts.legal import record_acceptance
        with transaction.atomic():
            published = publish_card(request.user, pk, version, conditions)
            record_acceptance(request, 'publication', {'card': str(published.pk),
                'revision': str(published.published_revision_id),
                'fields': list(published.published_revision.content.keys()), 'conditions': conditions})
    except Conflict as error:
        return HttpResponse(str(error), status=409)
    except ValidationError as error:
        return HttpResponse(' '.join(error.messages), status=422)
    messages.success(request, 'Визитка опубликована. Ссылка и QR остались прежними.')
    return redirect303(f'/app/cards/{pk}/edit')


@login_required
@require_POST
def unpublish(request, pk):
    unpublish_card(request.user, pk)
    messages.success(request, 'Публичный доступ закрыт.')
    return redirect303(f'/app/cards/{pk}/edit')


@login_required
@require_POST
def delete(request, pk):
    delete_card(request.user, pk)
    messages.success(request, 'Визитка удалена.')
    return redirect303('/app/cards')


@login_required
@never_cache
@require_GET
def qr(request, pk):
    card = own_card(request.user, pk)
    return qr_response(public_url(card))


@never_cache
@require_GET
def public_qr(request, public_id):
    return qr_response(public_url(public_card(public_id, workspace=getattr(request, 'domain_workspace', None))))


@never_cache
@require_GET
def public(request, public_id):
    from config.seo import card_metadata
    card = public_card(public_id, workspace=getattr(request, 'domain_workspace', None))
    response = render(request, 'cards/public.html', {'card': card, 'content': card.published_revision.content,
                      'seo': card_metadata(request, card),
                      'publication_conditions': card.published_revision.publication_conditions})
    from .analytics import record_view
    record_view(request, card)
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@never_cache
@require_GET
def vcard(request, public_id):
    card = public_card(public_id, workspace=getattr(request, 'domain_workspace', None))
    response = HttpResponse(render_vcard(card.published_revision.content, public_url(card)),
                            content_type='text/vcard; charset=utf-8')
    disposition = 'attachment' if request.GET.get('download') == '1' else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="contact.vcf"'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@require_GET
def live(request):
    return JsonResponse({'status': 'ok'})


@require_GET
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})
