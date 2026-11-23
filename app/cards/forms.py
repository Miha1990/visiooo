from django import forms
from copy import deepcopy
import re
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from .validation import validate_content
from .socials import SOCIAL_NETWORKS
from .image_slots import IMAGE_FIELDS
from .widgets import LinkButtonsWidget


class WebLinkField(forms.URLField):
    widget = forms.TextInput
    default_validators = [URLValidator(schemes=['http', 'https'])]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('assume_scheme', 'https')
        super().__init__(*args, **kwargs)
        self.widget.attrs.update({'inputmode':'url', 'autocapitalize':'none', 'spellcheck':'false'})

    def to_python(self, value):
        value = (value or '').strip()
        if re.match(r'^[^/:?#\s]+:[0-9]+(?:[/?#]|$)', value):
            value = 'https://' + value
        return super().to_python(value)


class CardForm(forms.Form):
    draft_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    name = forms.CharField(label='Имя и фамилия', max_length=100)
    title = forms.CharField(label='Должность', max_length=120, required=False)
    company = forms.CharField(label='Компания', max_length=160, required=False)
    bio = forms.CharField(label='О себе', max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 4}))
    phone_label = forms.CharField(label='Текст на кнопке', max_length=80, required=False,
        help_text='Например: «Позвонить» или «89289091817». Посетитель увидит только этот текст.')
    phone = forms.CharField(label='Номер телефона', required=False, max_length=40,
        widget=forms.TextInput(attrs={'type':'tel','inputmode':'tel','autocomplete':'tel','placeholder':'89289091817'}),
        help_text='Номер для звонка. Можно указать 8 (928) 909-18-17 или +7 928 909-18-17. Пустой номер скрывает кнопку.')
    email_label = forms.CharField(label='Текст на кнопке', max_length=80, required=False,
        help_text='Например: «Написать письмо». Адрес почты на кнопке не показывается.')
    email = forms.EmailField(label='Адрес электронной почты', required=False, max_length=254,
        help_text='На этот адрес откроется письмо. Пустой адрес скрывает кнопку.')
    website = WebLinkField(label='Сайт', required=False, max_length=2048,
        help_text='Можно указать google.com — https:// добавится автоматически.')
    template = forms.ChoiceField(label='Шаблон', choices=[('classic', 'Классический'),
                                                        ('minimal', 'Минимализм'), ('profile', 'Профиль')])
    accent = forms.RegexField(label='Акцентный цвет', regex=r'^#[0-9a-fA-F]{6}$',
                             widget=forms.TextInput(attrs={'type': 'color'}))
    links = forms.CharField(label='Кнопки со ссылками', required=False, widget=LinkButtonsWidget,
                            help_text='До 10 кнопок. Ссылку можно вводить без https://, например google.com. На визитке видно только название кнопки.')
    video_url = WebLinkField(label='Ссылка на видео', required=False, max_length=2048, assume_scheme='https',
        help_text='Рутуб, ВК Видео или Ютуб. Если оставить пустым, видеоблок не появится.')
    video_title = forms.CharField(label='Название видео', required=False, max_length=100)
    video_player = WebLinkField(label='Ссылка плеера ВК (при необходимости)', required=False, max_length=2048, assume_scheme='https',
        help_text='Если видео ВК не воспроизводится: «Поделиться → Экспортировать», скопируйте адрес src, включая hash, без HTML.')
    pdf_label = forms.CharField(label='Название кнопки PDF', required=False, max_length=100)
    map_address = forms.CharField(label='Адрес', required=False, max_length=300, help_text='Город, улица и дом. Пустой адрес скрывает карту.')
    map_latitude = forms.FloatField(label='Широта (необязательно)', required=False, min_value=-90, max_value=90)
    map_longitude = forms.FloatField(label='Долгота (необязательно)', required=False, min_value=-180, max_value=180)

    def __init__(self, *args, card=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.card = card
        self.design = deepcopy(card.draft.get('design')) if card else None
        from .client_content import available_blocks
        self.blocks = available_blocks(card.draft if card else {})
        if self.is_bound and self.data.get('template') in ('classic','minimal','profile'):
            self.blocks = available_blocks({})
        for block, names in self.block_field_names.items():
            for name in names:
                if block not in self.blocks: self.fields.pop(name)
        if self.design:
            self.fields['template'].choices = [('design', 'Из каталога: ' + self.design.get('sourceName', 'Мой шаблон'))] + list(self.fields['template'].choices)
            self.initial['template'] = 'design'
            self.fields['template'].help_text = 'После смены основы сохраните черновик, чтобы увидеть новый вид.'
            if not self.design['allowAccent'] and (not self.is_bound or self.data.get('template') == 'design'):
                self.fields['accent'].disabled = True
            if self.design['allowFont']:
                from .designs import FONTS
                self.fields['design_font'] = forms.ChoiceField(label='Шрифт шаблона', choices=FONTS, initial=self.design['font'])
        # The customer supplies content; visual style belongs to the template.
        if card and not card.workspace.owner.is_staff:
            self.fields['accent'].disabled = True
            self.fields['accent'].widget = forms.HiddenInput()
            if 'design_font' in self.fields:
                self.fields['design_font'].disabled = True
                self.fields['design_font'].widget = forms.HiddenInput()
        for key, label, placeholder in SOCIAL_NETWORKS:
            self.fields[f'social_{key}'] = WebLinkField(label=label, required=False, max_length=2048,
                assume_scheme='https', widget=forms.TextInput(attrs={
                    'placeholder': placeholder, 'data-social': key, 'data-label': label}))
        self.fields['website'].widget.attrs.update({'data-social': 'website', 'data-label': 'Сайт',
                                                   'placeholder': 'google.com'})

    @property
    def block_field_names(self):
        return {'video':['video_url','video_title','video_player'], 'document':['pdf_label'],
                'map':['map_address','map_latitude','map_longitude']}

    @property
    def content_fields(self):
        labels = {'video':'Видео', 'document':'PDF-файл', 'map':'Адрес на карте'}
        return [{'key':key,'label':labels[key],'fields':[self[name] for name in names if name in self.fields]}
                for key,names in self.block_field_names.items() if key in self.blocks]

    @property
    def details_fields(self):
        keys = ['name', 'title', 'company', 'bio', 'template', 'accent', 'links']
        if 'design_font' in self.fields:
            keys.append('design_font')
        return [self[key] for key in keys if not self.fields[key].widget.is_hidden]

    @property
    def contact_buttons(self):
        return [{'key': key, 'title': title, 'label_field': self[key+'_label'], 'target_field': self[key]}
                for key, title in [('phone', 'Телефон'), ('email', 'Электронная почта')]]

    def clean_phone(self):
        value = re.sub(r'[\s()\-]', '', self.cleaned_data.get('phone', ''))
        if len(value) == 11 and value.isascii() and value.isdigit() and value[0] in ('7','8'):
            value = '+7' + value[1:]
        if value and not re.fullmatch(r'\+[1-9][0-9]{7,14}', value):
            raise ValidationError('Укажите номер с кодом страны, например +79289091817, или российский номер 89289091817.')
        return value

    @property
    def social_fields(self):
        return [{'key': key, 'field': self[f'social_{key}']} for key, _, _ in SOCIAL_NETWORKS] + [
            {'key': 'website', 'field': self['website']}]

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        links = []
        for line in data.get('links', '').splitlines():
            if not line.strip():
                continue
            if '|' not in line:
                self.add_error('links', 'Укажите название и адрес через символ |.')
                return data
            label, url = line.split('|', 1)
            try:
                url = WebLinkField(required=True, max_length=2048).clean(url)
            except ValidationError as error:
                self.add_error('links', error)
                return data
            links.append({'label': label.strip(), 'url': url})
        content = {'schemaVersion': 1, 'links': links}
        for key in ('galleryAssetIds','video','document','map'):
            if self.card and key in self.card.draft:
                content[key] = deepcopy(self.card.draft[key])
        if 'video' in self.blocks:
            content.pop('video', None)
            if data.get('video_url'):
                content['video'] = {'url':data['video_url'], 'title':data.get('video_title',''), 'embedUrl':data.get('video_player','')}
        if 'document' in self.blocks:
            if data.get('pdf_label') or content.get('document', {}).get('assetId'):
                content.setdefault('document', {})['label'] = data.get('pdf_label','')
            else:
                content.pop('document', None)
        if 'map' in self.blocks:
            content.pop('map', None)
            if data.get('map_address'):
                content['map'] = {'address':data['map_address']}
                for key in ('latitude','longitude'):
                    if data.get('map_'+key) is not None: content['map'][key] = data['map_'+key]
        if data.get('template') == 'design' and self.design:
            content['design'] = deepcopy(self.design)
            data['template'] = self.card.draft['template']
            if self.design['allowFont']:
                content['design']['font'] = data['design_font']
        for asset_field in IMAGE_FIELDS.values():
            if self.card and self.card.draft.get(asset_field):
                content[asset_field] = self.card.draft[asset_field]
        socials = {key: data[f'social_{key}'] for key, _, _ in SOCIAL_NETWORKS if data.get(f'social_{key}')}
        if socials:
            content['socials'] = socials
        for key in ('name', 'title', 'company', 'bio', 'phone', 'email', 'website', 'template', 'accent'):
            if data.get(key):
                content[key] = data[key]
        for key, fallback in [('phone', 'Позвонить'), ('email', 'Написать')]:
            if data.get(key) or data.get(key+'_label'):
                content[key+'Label'] = data.get(key+'_label') or (self.design or {}).get(key+'Label') or fallback
        try:
            self.content = validate_content(content, workspace=self.card.workspace if self.card else None)
        except ValidationError as error:
            self.add_error(None, error)
        return data

    @classmethod
    def for_card(cls, card, data=None):
        initial = dict(card.draft, draft_version=card.draft_version)
        for key, fallback in [('phone', 'Позвонить'), ('email', 'Написать')]:
            initial[key+'_label'] = card.draft.get(key+'Label') or card.draft.get('design', {}).get(key+'Label') or fallback
        initial['links'] = '\n'.join(f'{link["label"]} | {link["url"]}' for link in card.draft['links'])
        initial.update({f'social_{key}': url for key, url in card.draft.get('socials', {}).items()})
        initial.update(video_url=card.draft.get('video',{}).get('url',''), video_title=card.draft.get('video',{}).get('title',''),
                       video_player=card.draft.get('video',{}).get('embedUrl',''), pdf_label=card.draft.get('document',{}).get('label',''),
                       map_address=card.draft.get('map',{}).get('address',''), map_latitude=card.draft.get('map',{}).get('latitude'),
                       map_longitude=card.draft.get('map',{}).get('longitude'))
        return cls(data=data, initial=initial, card=card)


class AvatarUploadForm(forms.Form):
    card_id = forms.UUIDField(widget=forms.HiddenInput)
    draft_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    image = forms.FileField(label='Фото', widget=forms.ClearableFileInput(attrs={
        'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='JPEG, PNG или WebP. До 5 МБ и 20 мегапикселей. Метаданные удаляются.')
    target = forms.ChoiceField(choices=[('avatar', 'Фото'), ('background', 'Фон'), ('header', 'Шапка')],
                              required=False, initial='avatar', widget=forms.HiddenInput)
