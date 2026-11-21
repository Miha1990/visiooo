from io import BytesIO
import uuid
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Sum

from workspaces.models import Workspace
from .models import Asset, Card
from .image_slots import IMAGE_FIELDS
from .services import own_card, workspace_for, active_subscription, save_card, Conflict

MAX_UPLOAD = 5 * 1024 * 1024
MAX_PIXELS = 20_000_000


def private_storage():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def normalize_image(upload):
    if upload.size > MAX_UPLOAD:
        raise ValidationError('Фото должно быть не больше 5 МБ.')
    raw = upload.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise ValidationError('Фото должно быть не больше 5 МБ.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValidationError('Разрешены только JPEG, PNG и WebP.')
                if source.width * source.height > MAX_PIXELS:
                    raise ValidationError('Фото должно содержать не больше 20 мегапикселей.')
                if getattr(source, 'n_frames', 1) != 1:
                    raise ValidationError('Выберите статичное изображение без анимации.')
                source.verify()
            with Image.open(BytesIO(raw)) as source:
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGBA')
                image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                # Fresh RGB canvas ensures EXIF, ICC, XMP and comments cannot survive.
                clean = Image.new('RGB', image.size, 'white')
                clean.paste(image, mask=image.getchannel('A'))
                output = BytesIO()
                clean.save(output, 'WEBP', quality=88, method=4)
                return output.getvalue(), clean.width, clean.height
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError('Не удалось прочитать фото. Загрузите исправный JPEG, PNG или WebP.') from error


def upload_avatar(user, pk, version, upload, target='avatar'):
    if target not in IMAGE_FIELDS:
        raise ValidationError('Выберите фон, фото или шапку визитки.')
    asset_field = IMAGE_FIELDS[target]
    # Reject foreign cards before spending resources on decoding.
    own_card(user, pk)
    data, width, height = normalize_image(upload)
    storage = private_storage()
    saved_key = None
    try:
        with transaction.atomic():
            workspace = Workspace.objects.select_for_update().get(pk=workspace_for(user).pk)
            card = Card.objects.select_for_update().get(pk=own_card(user, pk).pk)
            if card.draft_version != version:
                raise Conflict('Черновик изменился. Обновите страницу перед загрузкой фото.')
            limit = (50 if active_subscription(workspace) else 10) * 1024 * 1024
            used = Asset.objects.filter(workspace=workspace).aggregate(total=Sum('bytes'))['total'] or 0
            if used + len(data) > limit:
                raise ValidationError('Недостаточно места для фото. Лимит: 10 МБ до оплаты и 50 МБ с Профи.')
            saved_key = storage.save(f'{workspace.pk}/{uuid.uuid4().hex}.webp', ContentFile(data))
            asset = Asset.objects.create(workspace=workspace, object_key=saved_key, bytes=len(data),
                                          width=width, height=height)
            content = dict(card.draft)
            content[asset_field] = str(asset.pk)
            save_card(user, pk, version, content)
            return asset
    except Exception:
        if saved_key:
            storage.delete(saved_key)
        raise


@transaction.atomic
def remove_avatar(user, pk, version, target='avatar'):
    if target not in IMAGE_FIELDS:
        raise ValidationError('Некорректный тип фото.')
    card = own_card(user, pk)
    content = dict(card.draft)
    content.pop(IMAGE_FIELDS[target], None)
    save_card(user, pk, version, content)
