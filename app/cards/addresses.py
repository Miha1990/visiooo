import re
from django.core.exceptions import ValidationError
from .models import Card, CardAddress


def clean_address(value, card):
    value = (value or '').strip()
    if value == card.public_id:
        return value
    value = value.lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])', value):
        raise ValidationError('От 3 до 40 символов: латинские буквы, цифры и дефис внутри адреса.')
    if (Card.objects.filter(public_id__iexact=value).exclude(pk=card.pk).exists()
            or CardAddress.objects.filter(address__iexact=value).exclude(card=card).exists()):
        raise ValidationError('Этот адрес уже занят. Выберите другой.')
    return value
