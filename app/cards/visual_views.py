"""Shared visual editor and narrowly scoped media uploads."""
from copy import deepcopy
from io import BytesIO
import json
import uuid
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse, JsonResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from accounts.views import redirect303
from workspaces.models import Workspace
from .designs import editor_design, from_content, validate_design, validate_resources, icon_ids, BLOCKS
from .models import TemplatePhoto, TemplateIcon, Card, Asset
from .images import normalize_image, private_storage, upload_avatar
from .services import own_card, save_card, workspace_for, active_subscription, public_card, Conflict
from .asset_cleanup import referenced_asset_ids
from .template_icons import sanitize_svg
from .blocks import carousel_limit


def editor_context(content, user, *, template=False, card=None, example_pdf_url=''):
    from django.db.models import Q
    design = editor_design(from_content(content))
    content = deepcopy(content)
    content['design'] = design
    icons = TemplateIcon.objects.filter(Q(owner__isnull=True) | Q(owner=user))
    return {'content': content, 'visual_editor':True, 'editor_data': {'design': design, 'content': content,
            'template': template, 'blocks': dict(BLOCKS), 'carouselLimit': carousel_limit(),
            'samplePdfUrl':example_pdf_url,
            'icons': [{'id':str(i.pk),'name':i.name,'url':reverse('template_icon',args=[i.pk])} for i in icons],
            'uploadUrl': reverse('visual_media') if template else reverse('visual_card_media',args=[card.pk])}}


@login_required
@never_cache
@require_http_methods(['GET','POST'])
def edit(request, pk):
    card = own_card(request.user, pk)
    if not request.user.is_staff or not request.user.has_perm('cards.change_cardtemplate'):
        raise PermissionDenied
    content = deepcopy(card.draft)
    status = 200
    if request.method == 'POST':
        try:
            content = json.loads(request.POST.get('content', '{}'))
            if not isinstance(content, dict):
                raise ValidationError('Не удалось прочитать визитку.')
            validate_design(content.get('design'))
            validate_resources(content['design'], request.user)
            previous=card.draft.get('design',{})
            if previous.get('sourceId'):
                if not previous['allowAccent'] and content.get('accent') != card.draft['accent']:
                    raise ValidationError('В этом шаблоне акцентный цвет закреплён автором.')
                if not previous['allowFont'] and content['design']['font'] != previous['font']:
                    raise ValidationError('В этом шаблоне шрифт закреплён автором.')
                content['design']['allowAccent']=previous['allowAccent']
                content['design']['allowFont']=previous['allowFont']
            save_card(request.user, pk, int(request.POST.get('draft_version','0')), content)
        except Conflict as error:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'error':str(error)},status=409)
            messages.error(request, str(error)); status = 409
        except (ValueError, TypeError, ValidationError) as error:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'error':' '.join(error.messages) if isinstance(error,ValidationError) else 'Проверьте настройки визитки.'},status=422)
            messages.error(request, ' '.join(error.messages) if isinstance(error,ValidationError) else 'Проверьте настройки визитки.')
            content = deepcopy(card.draft); status = 422
        else:
            if request.headers.get('Accept') == 'application/json':
                return JsonResponse({'version':own_card(request.user,pk).draft_version})
            messages.success(request,'Визуальное оформление сохранено в черновике. Опубликуйте визитку в основном редакторе.')
            return redirect303(reverse('visual_card',args=[pk]))
    context = editor_context(content, request.user, card=card)
    return render(request,'visual/card.html',{'card':card, **context},status=status)


def upload_gallery(user, pk, version, upload):
    own_card(user, pk)
    data, width, height = normalize_image(upload)
    storage = private_storage(); key = None
    try:
        with transaction.atomic():
            workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
            card = own_card(user,pk)
            if card.draft_version != version:
                raise Conflict('Черновик изменился. Обновите страницу.')
            content = deepcopy(card.draft)
            photos = content.setdefault('galleryAssetIds',[])
            from .blocks import carousel_limit
            limit = carousel_limit()
            if len(photos) >= limit:
                raise ValidationError(f'В карусели может быть не больше {limit} фотографий. Удалите лишнюю и сохраните черновик.')
            refs = referenced_asset_ids(workspace.pk)
            used = Asset.objects.filter(workspace=workspace,pk__in=refs).aggregate(total=Sum('bytes'))['total'] or 0
            if used+len(data) > (50 if active_subscription(workspace) else 10)*1024*1024:
                raise ValidationError('Недостаточно места для фотографий.')
            key = storage.save(f'{workspace.pk}/{uuid.uuid4().hex}.webp',ContentFile(data))
            asset = Asset.objects.create(workspace=workspace,object_key=key,bytes=len(data),width=width,height=height)
            photos.append(str(asset.pk))
            save_card(user,pk,version,content)
            return asset
    except Exception:
        if key: storage.delete(key)
        raise


@login_required
@require_POST
def media(request, pk=None):
    if pk is None:
        if not request.user.is_staff or not request.user.has_perm('cards.change_cardtemplate'):
            raise PermissionDenied
    else:
        own_card(request.user,pk)
    upload = request.FILES.get('image')
    if not upload:
        return JsonResponse({'error':'Выберите файл.'},status=422)
    kind = request.POST.get('kind')
    try:
        if kind == 'icon':
            if not request.user.is_staff or not request.user.has_perm('cards.change_cardtemplate'):
                raise PermissionDenied
            shared = pk is None
            if shared and not request.user.has_perm('cards.add_templateicon'):
                raise PermissionDenied
            if not shared and TemplateIcon.objects.filter(owner=request.user).count() >= 100:
                raise ValidationError('Доступно до 100 собственных значков.')
            svg = sanitize_svg(upload.read(65537))
            item = TemplateIcon.objects.create(name='Значок блока',svg=svg,owner=None if shared else request.user)
            return JsonResponse({'id':str(item.pk),'url':reverse('template_icon',args=[item.pk]),'name':item.name})
        if kind == 'pdf':
            if pk is None:
                raise ValidationError('PDF загружается в личную визитку клиента. В шаблоне настройте оформление блока.')
            from .blocks import upload_pdf
            asset = upload_pdf(request.user,pk,int(request.POST.get('draft_version','0')),upload)
            return JsonResponse({'id':str(asset.pk),'url':reverse('preview_asset',args=[pk,asset.pk]),'version':own_card(request.user,pk).draft_version})
        if pk is None:
            data, _, _ = normalize_image(upload)
            item = TemplatePhoto.objects.create(name='Фото шаблона',image=data)
            return JsonResponse({'id':str(item.pk),'url':reverse('template_photo',args=[item.pk])})
        version = int(request.POST.get('draft_version','0'))
        if kind == 'gallery':
            asset = upload_gallery(request.user,pk,version,upload)
        elif kind in ('avatar','header','background'):
            asset = upload_avatar(request.user,pk,version,upload,target=kind)
        else:
            raise ValidationError('Выберите блок для загрузки изображения.')
        card = own_card(request.user,pk)
        return JsonResponse({'id':str(asset.pk),'url':reverse('preview_asset',args=[pk,asset.pk]),'version':card.draft_version})
    except Conflict as error:
        return JsonResponse({'error':str(error)},status=409)
    except (ValidationError,ValueError) as error:
        return JsonResponse({'error':' '.join(error.messages) if isinstance(error,ValidationError) else 'Проверьте версию черновика.'},status=422)


@require_safe
def photo(request, pk):
    item = get_object_or_404(TemplatePhoto,pk=pk)
    response = FileResponse(BytesIO(bytes(item.image)),content_type='image/webp')
    response['Cache-Control']='public, max-age=86400, immutable'
    response['X-Content-Type-Options']='nosniff'
    return response


def can_read_icon(request, item):
    if item.owner_id is None or (request.user.is_authenticated and request.user.pk == item.owner_id):
        return True
    for card in Card.objects.filter(workspace__owner_id=item.owner_id,status='published',blocked=False).select_related('published_revision','workspace'):
        if card.published_revision_id and str(item.pk) in icon_ids(card.published_revision.content.get('design',{})):
            try:
                public_card(card.public_id,workspace=getattr(request,'domain_workspace',None))
            except Http404:
                continue
            return True
    return False
