"""Customer content controls never accept layout definitions."""
from copy import deepcopy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from .services import own_card, save_card, Conflict


def available_blocks(content):
    design = content.get('design')
    if design:
        return set(design['blocks']) - set(design['hidden'])
    return {'cover','avatar','identity','bio','save','contacts','socials','carousel','video','document','map'}


def block_has_content(content, key):
    images = content.get('design', {}).get('images', {})
    if key == 'cover': return bool(content.get('headerAssetId') or images.get('header'))
    if key == 'avatar': return bool(content.get('avatarAssetId') or images.get('avatar'))
    if key == 'bio': return bool(content.get('bio', '').strip())
    if key == 'contacts': return bool(content.get('phone') or content.get('email') or content.get('links'))
    if key == 'socials': return bool(content.get('socials') or content.get('website'))
    if key == 'carousel':
        return bool(content['galleryAssetIds'] if 'galleryAssetIds' in content else content.get('design', {}).get('carousel', {}).get('photos'))
    if key == 'video': return bool(content.get('video', {}).get('url'))
    if key == 'document': return bool(content.get('document', {}).get('assetId'))
    if key == 'map': return bool(content.get('map', {}).get('address', '').strip())
    return True


@login_required
@require_POST
def media(request, pk):
    card = own_card(request.user, pk)
    try:
        version = int(request.POST.get('draft_version', '0'))
        if version != card.draft_version: raise Conflict('Черновик изменился. Обновите страницу.')
        operation = request.POST.get('operation')
        key = 'carousel' if operation in ('gallery','remove_photo','earlier','later') else 'document'
        if key not in available_blocks(card.draft):
            raise ValidationError('В выбранном шаблоне этот блок недоступен. Выберите другой шаблон.')
        if operation in ('gallery','pdf'):
            upload = request.FILES.get('file')
            if not upload: raise ValidationError('Выберите файл.')
            if operation == 'gallery':
                from .visual_views import upload_gallery
                upload_gallery(request.user, pk, version, upload)
            else:
                from .blocks import upload_pdf
                upload_pdf(request.user, pk, version, upload)
        else:
            content = deepcopy(card.draft)
            if operation == 'remove_pdf':
                content.get('document', {}).pop('assetId', None)
            elif operation in ('remove_photo','earlier','later'):
                photos = content.get('galleryAssetIds', [])
                index = photos.index(request.POST.get('asset_id'))
                if operation == 'remove_photo': photos.pop(index)
                else:
                    target = index + (-1 if operation == 'earlier' else 1)
                    if 0 <= target < len(photos): photos[index], photos[target] = photos[target], photos[index]
            else:
                raise ValidationError('Неизвестное действие.')
            save_card(request.user, pk, version, content)
        messages.success(request, 'Содержимое обновлено в черновике. Опубликуйте визитку, чтобы изменения стали видны посетителям.')
    except (ValueError, ValidationError, Conflict) as error:
        messages.error(request, ' '.join(error.messages) if isinstance(error, ValidationError) else str(error) if isinstance(error, Conflict) else 'Проверьте файл и обновите страницу.')
    return redirect(f'/app/cards/{pk}/edit#content-blocks')
