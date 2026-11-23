import re
from xml.etree import ElementTree as ET
from django.core.exceptions import ValidationError

SVG = 'http://www.w3.org/2000/svg'
TAGS = {'svg', 'g', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon',
        'defs', 'linearGradient', 'radialGradient', 'stop', 'clipPath', 'title', 'desc'}
ATTRS = {'viewBox', 'width', 'height', 'x', 'y', 'x1', 'x2', 'y1', 'y2', 'cx', 'cy', 'r', 'rx', 'ry',
         'd', 'points', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin',
         'fill-rule', 'clip-rule', 'opacity', 'fill-opacity', 'stroke-opacity', 'transform',
         'id', 'clip-path', 'gradientUnits', 'gradientTransform', 'offset', 'stop-color', 'stop-opacity'}


def sanitize_svg(raw):
    if len(raw) > 65536 or re.search(br'<!|<\?', raw):
        raise ValidationError('Значок: до 64 КБ, без деклараций, сущностей и инструкций XML.')
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError):
        raise ValidationError('Не удалось прочитать SVG.') from None
    if root.tag not in ('svg', f'{{{SVG}}}svg') or len(list(root.iter())) > 1000:
        raise ValidationError('Проверьте формат или сложность SVG.')
    for node in root.iter():
        tag = node.tag.removeprefix(f'{{{SVG}}}')
        if tag not in TAGS:
            raise ValidationError('SVG содержит неподдерживаемые элементы. Экспортируйте значок в виде контуров.')
        for key, value in node.attrib.items():
            if key not in ATTRS or len(value) > 30000 or any(ord(c) < 32 for c in value if c not in '\t\r\n'):
                raise ValidationError('SVG содержит неподдерживаемые атрибуты.')
            if key in ('fill', 'stroke', 'stop-color', 'clip-path'):
                if not re.fullmatch(r'(?:#[0-9a-fA-F]{3,8}|[A-Za-z]{1,24}|url\(#[A-Za-z_][A-Za-z0-9_-]{0,60}\))', value):
                    raise ValidationError('SVG: разрешены только цвета и внутренние ссылки на градиенты.')
            elif key == 'id':
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,60}', value):
                    raise ValidationError('SVG: некорректный идентификатор.')
            elif not re.fullmatch(r'[A-Za-z0-9.,+()\-\s%]*', value):
                raise ValidationError('SVG: некорректное значение атрибута.')
        if tag not in ('title', 'desc'):
            node.text = None
        node.tail = None
    ET.register_namespace('', SVG)
    return ET.tostring(root, encoding='unicode')
