"""Customer media controls preserve validated content and responsive sizes."""
from copy import deepcopy
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .services import own_card, save_card, Conflict


def available_blocks(content):
    design = content.get('design')
    if design:
        return set(design['blocks']) - set(design['hidden'])
    return {'cover','avatar','identity','bio','save','contacts','socials','carousel','video','document','map'}


def block_has_content(content, key):
    images = content.get('design', {}).get('images', {})
    if key == 'cover': return bool(content.get('headerAssetId') or content.get('logoAssetId') or images.get('header'))
    if key == 'avatar': return bool(content.get('avatarAssetId') or images.get('avatar'))
    if key == 'bio': return bool(content.get('bio', '').strip())
    if key == 'contacts':
        if content.get('buttonLayout') == 'tiles':
            return any(item['kind'] != 'file' or item['value'] or content.get('document', {}).get('assetId') for item in content.get('buttons', []))
        return bool(content.get('phone') or content.get('email') or content.get('links'))
    if key == 'socials': return False if content.get('buttonLayout') == 'tiles' else bool(content.get('socials') or content.get('website'))
    if key == 'carousel':
        return bool(content['galleryAssetIds'] if 'galleryAssetIds' in content else content.get('design', {}).get('carousel', {}).get('photos'))
    if key == 'video':
        from .blocks import video_items
        return bool(video_items(content))
    if key == 'document': return content.get('buttonLayout') != 'tiles' and bool(content.get('document', {}).get('assetId'))
    if key == 'map': return bool(content.get('map', {}).get('address', '').strip())
    return True


@login_required
@require_POST
def media(request, pk):
    card = own_card(request.user, pk)
    ajax = 'application/json' in request.headers.get('Accept', '')
    try:
        version = int(request.POST.get('draft_version', '0'))
        if version != card.draft_version: raise Conflict('Черновик изменился. Обновите страницу.')
        operation = request.POST.get('operation')
        key = 'carousel' if operation in ('gallery','remove_photo','earlier','later','reorder_gallery') else 'document'
        if key not in available_blocks(card.draft):
            raise ValidationError('В выбранном шаблоне этот блок недоступен. Выберите другой шаблон.')
        if operation in ('gallery','pdf'):
            upload = request.FILES.get('file')
            if not upload: raise ValidationError('Выберите файл.')
            if operation == 'gallery':
                from .visual_views import upload_gallery_many
                upload_gallery_many(request.user, pk, version, request.FILES.getlist('file'))
            else:
                from .blocks import upload_pdf
                upload_pdf(request.user, pk, version, upload)
        else:
            content = deepcopy(card.draft)
            if operation == 'remove_pdf':
                content.get('document', {}).pop('assetId', None)
            elif operation == 'reorder_gallery':
                order = json.loads(request.POST.get('order', '[]'))
                photos = content.get('galleryAssetIds', [])
                if not isinstance(order, list) or not all(isinstance(item, str) for item in order) or len(order) != len(photos) or len(set(order)) != len(order) or set(order) != set(photos):
                    raise ValidationError('Список фотографий изменился. Обновите страницу.')
                content['galleryAssetIds'] = order
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
        if ajax:
            card.refresh_from_db()
            return JsonResponse({'version':card.draft_version,'gallery':card.draft.get('galleryAssetIds',[])})
        messages.success(request, 'Содержимое обновлено в черновике. Опубликуйте визитку, чтобы изменения стали видны посетителям.')
    except (ValueError, ValidationError, Conflict) as error:
        if ajax:
            return JsonResponse({'error':' '.join(error.messages) if isinstance(error, ValidationError) else str(error) if isinstance(error, Conflict) else 'Проверьте фотографии и обновите страницу.'},status=409 if isinstance(error, Conflict) else 400)
        messages.error(request, ' '.join(error.messages) if isinstance(error, ValidationError) else str(error) if isinstance(error, Conflict) else 'Проверьте файл и обновите страницу.')
    return redirect(f'/app/cards/{pk}/edit#content-blocks')
