import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from jsonschema import Draft202012Validator, FormatChecker
from .image_slots import IMAGE_FIELDS, content_asset_ids

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / 'card.schema.json').read_text(encoding='utf-8'))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def validate_content(content, workspace=None):
    errors = sorted(VALIDATOR.iter_errors(content), key=lambda error: str(error.path))
    if errors:
        raise ValidationError('Проверьте содержимое: ' + '; '.join(
            f'{" / ".join(map(str, error.path))}: {error.message}' for error in errors))
    if content.get('design'):
        from .designs import validate_design, contrast
        validate_design(content['design'])
        if content['design']['buttonStyle'] == 'outline' and contrast(content['accent'], content['design']['background']) < 4.5:
            raise ValidationError('Цвет контурных кнопок должен хорошо отличаться от фона.')
    if 'buttons' in content:
        from .button_builder import clean_buttons
        if clean_buttons(content['buttons']) != content['buttons']:
            raise ValidationError('Проверьте номера телефонов и ссылки в кнопках.')
    from .models import Asset
    from .blocks import video_embed
    video = content.get('video', {})
    if video.get('url'):
        video_embed(video['url'], video.get('embedUrl', ''))
    elif video.get('embedUrl'):
        raise ValidationError('Сначала укажите ссылку на видео.')
    location = content.get('map', {})
    if ('latitude' in location) != ('longitude' in location):
        raise ValidationError('Укажите обе координаты точки.')
    if any(not math.isfinite(location[key]) for key in ('latitude','longitude') if key in location):
        raise ValidationError('Координаты должны быть конечными числами.')
    for asset_id in content_asset_ids(content):
        expected = 'pdf' if asset_id == content.get('document', {}).get('assetId') else 'image'
        if workspace is None or not Asset.objects.filter(pk=asset_id, workspace=workspace, kind=expected).exists():
            raise ValidationError('Файл недоступен. Загрузите его в своём аккаунте.')
    image_ids = {content.get(field) for field in IMAGE_FIELDS.values()} | set(content.get('galleryAssetIds', []))
    if content.get('document', {}).get('assetId') in image_ids - {None}:
        raise ValidationError('PDF нельзя использовать вместо фотографии.')
    if content.get('email'):
        validate_email(content['email'])
    urls = [link['url'] for link in content['links']]
    urls.extend(content.get('socials', {}).values())
    if content.get('website'):
        urls.append(content['website'])
    for url in urls:
        URLValidator(schemes=['http', 'https'])(url)
        parsed = urlsplit(url)
        if parsed.username or parsed.password or any(ord(c) < 32 for c in url):
            raise ValidationError('Ссылки не должны содержать логин, пароль или управляющие символы.')
    # All action buttons use white text. Enforce WCAG AA contrast on the server.
    channels = [int(content['accent'][i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    luminance = sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))
    if 1.05 / (luminance + 0.05) < 4.5:
        raise ValidationError('Выберите более тёмный акцентный цвет для читаемого текста кнопок.')
    return content
