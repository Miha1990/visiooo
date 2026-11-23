"""Block policies and allowlisted third party embeds; never fetch user supplied URLs."""
from copy import deepcopy
import re
import uuid
from urllib.parse import urlsplit, parse_qs, urlencode
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum
from workspaces.models import Workspace
from .models import Asset, CardBlockSettings


def carousel_limit():
    return CardBlockSettings.objects.filter(pk=1).values_list('carousel_limit', flat=True).first() or 10


def validate_gallery_limit(content, previous):
    def count(value):
        return max(len(value.get('galleryAssetIds', [])), len(value.get('design', {}).get('carousel', {}).get('photos', [])))
    limit = carousel_limit()
    if count(content) > max(limit, count(previous)):
        raise ValidationError(f'В карусели доступно до {limit} фотографий.')


def parsed_url(value):
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443) or any(ord(c) < 33 for c in value):
            raise ValueError
        return url, (url.hostname or '').removeprefix('www.'), parse_qs(url.query)
    except ValueError:
        raise ValidationError('Используйте полную ссылку HTTPS на поддерживаемый сервис.')


def video_embed(value, override=''):
    url, host, query = parsed_url(value)
    if host in ('youtube.com', 'm.youtube.com', 'youtu.be', 'youtube-nocookie.com'):
        video_id = url.path.strip('/') if host == 'youtu.be' else query.get('v', [''])[0]
        match = re.fullmatch(r'/(?:shorts|embed|live)/([\w-]{11})/?', url.path)
        if match: video_id = match[1]
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            if override: raise ValidationError('Дополнительная ссылка плеера нужна только для ВК Видео.')
            return 'https://www.youtube-nocookie.com/embed/' + video_id
    elif host == 'rutube.ru':
        match = re.fullmatch(r'/(?:video/(?:private/)?|play/embed/)([a-fA-F0-9]{32})/?', url.path)
        if match:
            if override: raise ValidationError('Дополнительная ссылка плеера нужна только для ВК Видео.')
            result = 'https://rutube.ru/play/embed/' + match[1]
            key = query.get('p', [''])[0]
            if key:
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', key): raise ValidationError('Некорректный ключ видео.')
                result += '/?' + urlencode({'p':key})
            return result
    elif host in ('vk.com', 'm.vk.com', 'vkvideo.ru'):
        match = re.fullmatch(r'/video(-?\d{1,20})_(\d{1,20})/?', url.path)
        if url.path == '/video_ext.php' or match:
            if override:
                player, player_host, params = parsed_url(override)
                if player_host not in ('vk.com', 'vkvideo.ru') or player.path != '/video_ext.php':
                    raise ValidationError('Ссылка плеера должна вести на ВК Видео.')
            else: params = query if not match else {'oid':[match[1]],'id':[match[2]]}
            oid, video_id, key = (params.get(k, [''])[0] for k in ('oid','id','hash'))
            if not re.fullmatch(r'-?\d{1,20}', oid) or not re.fullmatch(r'\d{1,20}', video_id):
                raise ValidationError('Проверьте ссылку ВК Видео.')
            if match and (oid != match[1] or video_id != match[2]):
                raise ValidationError('Ссылка плеера относится к другому видео.')
            if key and not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', key):
                raise ValidationError('Проверьте ключ плеера ВК Видео.')
            params = {'oid':oid,'id':video_id}
            if key: params['hash'] = key
            return 'https://vk.com/video_ext.php?' + urlencode(params)
    raise ValidationError('Поддерживаются ссылки на отдельные видео Рутуб, ВК Видео и Ютуб.')


def map_embed(location):
    if not location.get('address'): return ''
    if 'latitude' in location and 'longitude' in location:
        point = f"{location['longitude']},{location['latitude']}"
        return 'https://yandex.ru/map-widget/v1/?' + urlencode({'ll':point,'pt':point+',pm2rdm','z':16})
    return 'https://yandex.ru/map-widget/v1/?' + urlencode({'text':location['address'],'z':16})


def upload_pdf(user, pk, version, upload):
    from .images import private_storage
    from .services import own_card, workspace_for, save_card, active_subscription, Conflict
    from .asset_cleanup import referenced_asset_ids
    own_card(user, pk)
    limit = 10 * 1024 * 1024
    if upload.size > limit: raise ValidationError('PDF должен быть не больше 10 МБ.')
    data = upload.read(limit+1)
    if len(data) > limit or not data.startswith(b'%PDF-') or b'%%EOF' not in data[-4096:]:
        raise ValidationError('Выберите файл в формате PDF размером до 10 МБ.')
    storage = private_storage(); key = None
    try:
        with transaction.atomic():
            workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
            card = own_card(user, pk)
            if card.draft_version != version: raise Conflict('Черновик изменился. Обновите страницу.')
            used = Asset.objects.filter(workspace=workspace, pk__in=referenced_asset_ids(workspace.pk)).aggregate(total=Sum('bytes'))['total'] or 0
            if used + len(data) > (50 if active_subscription(workspace) else 10)*1024*1024:
                raise ValidationError('Недостаточно места для файла. Удалите неиспользуемые файлы.')
            key = storage.save(f'{workspace.pk}/{uuid.uuid4().hex}.pdf', ContentFile(data))
            asset = Asset.objects.create(workspace=workspace, object_key=key, kind='pdf', bytes=len(data), width=0, height=0)
            content = deepcopy(card.draft)
            content['document'] = {**content.get('document', {}), 'assetId':str(asset.pk)}
            save_card(user, pk, version, content)
            return asset
    except Exception:
        if key: storage.delete(key)
        raise
