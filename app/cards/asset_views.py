from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from accounts.views import redirect303
from .forms import AvatarUploadForm
from .images import private_storage, upload_avatar, remove_avatar
from .models import Asset
from .image_slots import IMAGE_FIELDS, content_asset_ids
from .services import own_card, public_card, Conflict


def image_response(asset):
    try:
        photo = private_storage().open(asset.object_key, 'rb')
    except FileNotFoundError:
        raise Http404
    response = FileResponse(photo, content_type='image/webp')
    response['X-Robots-Tag'] = 'noindex, nofollow'
    response['Content-Disposition'] = 'inline; filename="photo.webp"'
    return response


@login_required
@require_POST
def upload(request):
    form = AvatarUploadForm(request.POST, request.FILES)
    if form.is_valid():
        pk = form.cleaned_data['card_id']
        own_card(request.user, pk)
        try:
            upload_avatar(request.user, pk, form.cleaned_data['draft_version'], form.cleaned_data['image'],
                          target=form.cleaned_data.get('target') or 'avatar')
        except Conflict as error:
            form.add_error(None, str(error))
            return render(request, 'cards/upload_error.html', {'form': form, 'pk': pk}, status=409)
        except ValidationError as error:
            form.add_error('image', error)
        else:
            messages.success(request, 'Изображение добавлено в черновик. Опубликуйте, чтобы обновить визитку.')
            return redirect303(f'/app/cards/{pk}/edit')
    pk = form.cleaned_data.get('card_id')
    if pk:
        own_card(request.user, pk)
    return render(request, 'cards/upload_error.html', {'form': form, 'pk': pk}, status=422)


@login_required
@require_POST
def remove(request, pk):
    own_card(request.user, pk)
    try:
        version = int(request.POST.get('draft_version', '0'))
        remove_avatar(request.user, pk, version, target=request.POST.get('target', 'avatar'))
    except (ValueError, ValidationError):
        return HttpResponse('Проверьте версию черновика.', status=422)
    except Conflict as error:
        return HttpResponse(str(error), status=409)
    messages.success(request, 'Фото убрано из черновика. Опубликованная версия пока не изменилась.')
    return redirect303(f'/app/cards/{pk}/edit')


@login_required
@never_cache
@require_GET
def preview(request, pk, asset_id):
    card = own_card(request.user, pk)
    if str(asset_id) not in content_asset_ids(card.draft):
        raise Http404
    asset = get_object_or_404(Asset, pk=asset_id, workspace=card.workspace)
    return image_response(asset)


@never_cache
@require_GET
def public(request, public_id, asset_id):
    card = public_card(public_id, workspace=getattr(request, 'domain_workspace', None))
    content = card.published_revision.content
    if str(asset_id) not in content_asset_ids(content):
        raise Http404
    asset = get_object_or_404(Asset, pk=asset_id, workspace=card.workspace)
    return image_response(asset)
