"""Bounded presentation settings. Published cards hold their own immutable snapshot."""
from copy import deepcopy
import math
from django.core.exceptions import ValidationError
from jsonschema import Draft202012Validator, FormatChecker
from .validation import SCHEMA

DESIGN_VALIDATOR=Draft202012Validator({'$ref':'#/$defs/design','$defs':SCHEMA['$defs']},format_checker=FormatChecker())

BLOCKS = [('cover', 'Шапка'), ('avatar', 'Фото'), ('identity', 'Имя и должность'),
          ('bio', 'О себе'), ('save', 'Сохранение контакта'), ('contacts', 'Контакты и ссылки'), ('socials', 'Соцсети'), ('carousel', 'Карусель фотографий'), ('video', 'Видео'), ('document', 'PDF-файл'), ('map', 'Адрес на карте')]
FONTS = [('ui', 'Современный'), ('serif', 'Книжный'), ('rounded', 'Мягкий')]
FONT_CSS = {'ui': "'Segoe UI',system-ui,sans-serif", 'serif': 'Georgia,serif', 'rounded': "'Trebuchet MS',Arial,sans-serif"}
ICON_ROLES = [('save', 'Сохранение контакта'), ('phone', 'Телефон'), ('email', 'Почта'), ('link', 'Дополнительные ссылки'),
              ('telegram', 'Телеграм'), ('vk', 'ВКонтакте'), ('ok', 'Одноклассники'), ('max', 'Макс'),
              ('instagram', 'Инстаграм'), ('threads', 'Тредс'), ('avito', 'Авито'), ('website', 'Сайт')]
DEFAULT = {'blocks': [key for key, _ in BLOCKS if key not in ('carousel','video','document','map')], 'hidden': [], 'accent': '#2457DB',
    'background': '#FFFFFF', 'text': '#17272D', 'font': 'ui', 'align': 'left',
    'buttonShape': 'rounded', 'buttonStyle': 'filled', 'buttonColumns': 1, 'iconPosition': 'left',
    'iconSize': 24, 'avatarShape': 'circle', 'avatarSize': 96, 'coverHeight': 130,
    'gap': 16, 'radius': 20, 'nameSize': 30, 'weight': 700, 'socialMode': 'both',
    'caption': 'ПРИЯТНО ПОЗНАКОМИТЬСЯ', 'saveLabel': 'Сохранить контакт',
    'phoneLabel': 'Позвонить', 'emailLabel': 'Написать', 'socialLabel': 'Соцсети и сайт',
    'icons': {}, 'allowAccent': True, 'allowFont': False}


def contrast(a, b):
    def luminance(value):
        channels = [int(value[index:index+2], 16) / 255 for index in (1, 3, 5)]
        return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * weight
                   for v, weight in zip(channels, (.2126, .7152, .0722)))
    x, y = sorted([luminance(a), luminance(b)])
    return (y + .05) / (x + .05)


def validate_design(value):
    errors = list(DESIGN_VALIDATOR.iter_errors(value))
    if errors:
        raise ValidationError('Проверьте настройки оформления: недопустимое значение или неполный набор блоков.')
    if value.get('canvas', {}).get('enabled') and any(key not in value.get('frames', {}) for key in value['blocks']):
        raise ValidationError('Для свободного холста задайте положение всех блоков.')
    for frame in value.get('frames', {}).values():
        if any(not math.isfinite(frame[key]) for key in ('x','y','width','height')):
            raise ValidationError('Координаты и размеры должны быть конечными числами.')
        if frame['unit'] == '%' and (frame['width'] > 100 or frame['x'] + frame['width'] > 100.1):
            raise ValidationError('Адаптивный блок должен помещаться по ширине холста.')
    if contrast(value['text'], value['background']) < 4.5:
        raise ValidationError('Цвет текста должен хорошо отличаться от фона.')
    if contrast(value['accent'], '#FFFFFF') < 4.5:
        raise ValidationError('Выберите более тёмный акцент для белых надписей кнопок.')
    if value['buttonStyle'] == 'outline' and contrast(value['accent'], value['background']) < 4.5:
        raise ValidationError('Цвет контурных кнопок должен хорошо отличаться от фона.')
    return value


def from_content(content):
    if content.get('design'):
        value=deepcopy(content['design'])
        value['accent']=content.get('accent',value['accent'])
        return validate_design(value)
    value = deepcopy(DEFAULT)
    value['accent'] = content.get('accent', DEFAULT['accent'])
    if content.get('template') == 'minimal':
        value.update(font='serif', avatarShape='rounded', buttonStyle='outline', radius=8, coverHeight=75)
    elif content.get('template') == 'profile':
        value.update(align='center', avatarSize=130, coverHeight=150, buttonShape='pill')
    return value


def block_settings(design, key):
    """Resolve optional block overrides without changing older published designs."""
    override = design.get('blockStyles', {}).get(key, {})
    return {
        'align': override.get('align', 'inherit'),
        'iconPosition': override.get('iconPosition', 'inherit'),
        'effectiveIconPosition': design['iconPosition'] if override.get('iconPosition', 'inherit') == 'inherit' else override['iconPosition'],
        'iconSize': override.get('iconSize', design['iconSize']),
        'icon': override.get('icon', ''),
        'buttonShape': override.get('buttonShape', 'inherit'),
        'buttonCorners': override.get('buttonCorners', design.get('buttonCorners')),
    }


def editor_design(value):
    value = deepcopy(value)
    for key in ('carousel','video','document','map'):
        if key not in value['blocks']:
            value['blocks'].append(key)
            value['hidden'].append(key)
            if value.get('canvas',{}).get('enabled'):
                value.setdefault('frames',{})[key]={'x':6,'y':0,'width':88,'unit':'%','height':0,'z':1,'corners':[0,0,0,0]}
    value.setdefault('carousel', {'photos': [], 'visible': 1, 'height': 220, 'autoplay': False, 'interval': 5})
    return value


def frame_css(design, key):
    frame = design.get('frames', {}).get(key)
    if not frame or not design.get('canvas', {}).get('enabled'):
        return ''
    width = f"{frame['width']}%" if frame['unit'] == '%' else f"calc({frame['width']}px * var(--canvas-scale,1))"
    height = f"calc({frame['height']}px * var(--canvas-scale,1))" if frame['height'] else 'auto'
    return f"left:{frame['x']}%;top:calc({frame['y']}px * var(--canvas-scale,1));width:{width};height:{height};z-index:{frame['z']};--frame-radius:" + ' '.join(f'{v}px' for v in frame['corners'])


def icon_ids(design):
    return set(design.get('icons', {}).values()) | {v['icon'] for v in design.get('blockStyles', {}).values() if v.get('icon')}


def validate_resources(design, user):
    from django.db.models import Q
    from .models import TemplateIcon, TemplatePhoto
    ids = icon_ids(design)
    allowed = TemplateIcon.objects.filter(Q(owner__isnull=True) | Q(owner=user), pk__in=ids)
    if allowed.count() != len(ids):
        raise ValidationError('Один из значков недоступен вашему аккаунту.')
    photos = set(design.get('images', {}).values()) | set(design.get('carousel', {}).get('photos', []))
    if TemplatePhoto.objects.filter(pk__in=photos).count() != len(photos):
        raise ValidationError('Одно из изображений шаблона недоступно.')


def css(value):
    value = validate_design(value)
    radius = {'square': 0, 'rounded': 16, 'circle': 999}[value['avatarShape']]
    buttons = {'rect': 0, 'rounded': 12, 'pill': 999}[value['buttonShape']]
    return ';'.join(f'--{key}:{val}' for key, val in {
        'design-bg': value['background'], 'design-text': value['text'], 'design-font': FONT_CSS[value['font']],
        'design-align': value['align'], 'design-gap': f"{value['gap']}px", 'design-radius': f"{value['radius']}px",
        'design-avatar': f"{value['avatarSize']}px", 'design-avatar-radius': f'{radius}px',
        'design-cover': f"{value['coverHeight']}px", 'design-button-radius': ' '.join(f'{v}px' for v in value['buttonCorners']) if 'buttonCorners' in value else f'{buttons}px',
        'design-icon': f"{value['iconSize']}px", 'design-name': f"{value['nameSize']}px",
        'design-weight': value['weight'], 'design-columns': value['buttonColumns'],
    }.items())
