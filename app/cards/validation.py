import json
from pathlib import Path
from urllib.parse import urlsplit
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email
from jsonschema import Draft202012Validator, FormatChecker
from .image_slots import IMAGE_FIELDS

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / 'card.schema.json').read_text(encoding='utf-8'))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def validate_content(content, workspace=None):
    errors = sorted(VALIDATOR.iter_errors(content), key=lambda error: str(error.path))
    if errors:
        raise ValidationError('Проверьте содержимое: ' + '; '.join(
            f'{" / ".join(map(str, error.path))}: {error.message}' for error in errors))
    from .models import Asset
    for asset_field in IMAGE_FIELDS.values():
        if asset_field in content:
            if workspace is None or not Asset.objects.filter(pk=content[asset_field], workspace=workspace).exists():
                raise ValidationError('Фото недоступно. Загрузите изображение в своём аккаунте.')
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
