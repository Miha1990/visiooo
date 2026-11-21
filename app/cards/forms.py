from django import forms
from django.core.exceptions import ValidationError
from .validation import validate_content
from .socials import SOCIAL_NETWORKS
from .image_slots import IMAGE_FIELDS


class CardForm(forms.Form):
    draft_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    name = forms.CharField(label='Имя и фамилия', max_length=100)
    title = forms.CharField(label='Должность', max_length=120, required=False)
    company = forms.CharField(label='Компания', max_length=160, required=False)
    bio = forms.CharField(label='О себе', max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 4}))
    phone = forms.RegexField(label='Телефон', regex=r'^\+[1-9][0-9]{7,14}$', required=False,
                            help_text='Международный формат: +79991234567')
    email = forms.EmailField(label='Публичная электронная почта', required=False, max_length=254)
    website = forms.URLField(label='Сайт', required=False, max_length=2048, assume_scheme='https')
    template = forms.ChoiceField(label='Шаблон', choices=[('classic', 'Классический'),
                                                        ('minimal', 'Минимализм'), ('profile', 'Профиль')])
    accent = forms.RegexField(label='Акцентный цвет', regex=r'^#[0-9a-fA-F]{6}$',
                             widget=forms.TextInput(attrs={'type': 'color'}))
    links = forms.CharField(label='Дополнительные ссылки', required=False, widget=forms.Textarea(attrs={'rows': 4}),
                            help_text='До 10 ссылок, каждая с новой строки: Название | https://example.ru')

    def __init__(self, *args, card=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.card = card
        for key, label, placeholder in SOCIAL_NETWORKS:
            self.fields[f'social_{key}'] = forms.URLField(label=label, required=False, max_length=2048,
                assume_scheme='https', widget=forms.URLInput(attrs={
                    'placeholder': placeholder, 'data-social': key, 'data-label': label}))
        self.fields['website'].widget.attrs.update({'data-social': 'website', 'data-label': 'Сайт',
                                                   'placeholder': 'https://example.ru'})

    @property
    def details_fields(self):
        return [self[key] for key in ('name', 'title', 'company', 'bio', 'phone', 'email', 'template', 'accent', 'links')]

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
            links.append({'label': label.strip(), 'url': url.strip()})
        content = {'schemaVersion': 1, 'links': links}
        for asset_field in IMAGE_FIELDS.values():
            if self.card and self.card.draft.get(asset_field):
                content[asset_field] = self.card.draft[asset_field]
        socials = {key: data[f'social_{key}'] for key, _, _ in SOCIAL_NETWORKS if data.get(f'social_{key}')}
        if socials:
            content['socials'] = socials
        for key in ('name', 'title', 'company', 'bio', 'phone', 'email', 'website', 'template', 'accent'):
            if data.get(key):
                content[key] = data[key]
        try:
            self.content = validate_content(content, workspace=self.card.workspace if self.card else None)
        except ValidationError as error:
            self.add_error(None, error)
        return data

    @classmethod
    def for_card(cls, card, data=None):
        initial = dict(card.draft, draft_version=card.draft_version)
        initial['links'] = '\n'.join(f'{link["label"]} | {link["url"]}' for link in card.draft['links'])
        initial.update({f'social_{key}': url for key, url in card.draft.get('socials', {}).items()})
        return cls(data=data, initial=initial, card=card)


class AvatarUploadForm(forms.Form):
    card_id = forms.UUIDField(widget=forms.HiddenInput)
    draft_version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    image = forms.FileField(label='Фото', widget=forms.ClearableFileInput(attrs={
        'accept': 'image/jpeg,image/png,image/webp'}),
        help_text='JPEG, PNG или WebP. До 5 МБ и 20 мегапикселей. Метаданные удаляются.')
    target = forms.ChoiceField(choices=[('avatar', 'Фото'), ('background', 'Фон'), ('header', 'Шапка')],
                              required=False, initial='avatar', widget=forms.HiddenInput)
