from copy import deepcopy
from django import forms
from .designs import BLOCKS, FONTS, ICON_ROLES, DEFAULT, validate_design, block_settings
from .models import TemplateIcon
from .template_icons import sanitize_svg


class TemplateForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    visual_design = forms.JSONField(required=False, widget=forms.HiddenInput)
    name = forms.CharField(label='Название шаблона', max_length=100)
    description = forms.CharField(label='Описание для клиентов', max_length=300, required=False)
    category = forms.CharField(label='Категория', max_length=60, required=False)
    position = forms.IntegerField(label='Порядок в каталоге', min_value=0, max_value=9999, initial=0)
    block_order = forms.CharField(widget=forms.HiddenInput)
    hidden = forms.MultipleChoiceField(label='Скрытые блоки', choices=[item for item in BLOCKS if item[0] not in ('identity','save')],
        required=False, widget=forms.CheckboxSelectMultiple)
    accent = forms.RegexField(label='Акцентный цвет', regex=r'^#[0-9a-fA-F]{6}$', widget=forms.TextInput(attrs={'type':'color'}))
    background = forms.RegexField(label='Фон карточки', regex=r'^#[0-9a-fA-F]{6}$', widget=forms.TextInput(attrs={'type':'color'}))
    text = forms.RegexField(label='Цвет текста', regex=r'^#[0-9a-fA-F]{6}$', widget=forms.TextInput(attrs={'type':'color'}))
    font = forms.ChoiceField(label='Шрифт', choices=FONTS)
    align = forms.ChoiceField(label='Общее выравнивание', choices=[('left','По левому краю'),('center','По центру')])
    nameSize = forms.IntegerField(label='Размер имени', min_value=22, max_value=40)
    weight = forms.TypedChoiceField(label='Насыщенность имени', choices=[(400,'Обычная'),(600,'Полужирная'),(700,'Жирная')], coerce=int)
    buttonShape = forms.ChoiceField(label='Форма кнопок', choices=[('rect','Прямоугольные'),('rounded','Скруглённые'),('pill','Овальные')])
    buttonStyle = forms.ChoiceField(label='Оформление кнопок', choices=[('filled','С заливкой'),('outline','Контурные')])
    buttonColumns = forms.TypedChoiceField(label='Расположение кнопок', choices=[(1,'Одна колонка'),(2,'Две колонки')], coerce=int)
    iconPosition = forms.ChoiceField(label='Общее положение значков', choices=[('left','Слева'),('right','Справа'),('top','Сверху')])
    iconSize = forms.IntegerField(label='Общий размер значков', min_value=16, max_value=36)
    socialMode = forms.ChoiceField(label='Кнопки соцсетей', choices=[('both','Значок и подпись'),('icons','Круглые значки'),('radial','Контакты по кругу')])
    avatarShape = forms.ChoiceField(label='Форма фотографии', choices=[('circle','Круг'),('rounded','Скруглённый квадрат'),('square','Квадрат')])
    avatarSize = forms.IntegerField(label='Размер фотографии', min_value=64, max_value=144)
    coverHeight = forms.IntegerField(label='Высота шапки', min_value=60, max_value=240)
    gap = forms.IntegerField(label='Отступ между блоками', min_value=8, max_value=32)
    radius = forms.IntegerField(label='Скругление карточки', min_value=0, max_value=36)
    caption = forms.CharField(label='Надпись в шапке', max_length=60, required=False)
    saveLabel = forms.CharField(label='Кнопка сохранения контакта', max_length=60)
    phoneLabel = forms.CharField(label='Кнопка звонка', max_length=60)
    emailLabel = forms.CharField(label='Кнопка письма', max_length=60)
    socialLabel = forms.CharField(label='Заголовок соцсетей', max_length=60)
    allowAccent = forms.BooleanField(label='Клиент может менять акцентный цвет', required=False)
    allowFont = forms.BooleanField(label='Клиент может менять шрифт', required=False)

    def __init__(self, *args, item, **kwargs):
        self.item = item
        design = deepcopy(DEFAULT)
        design.update(item.draft)
        initial = {**design, 'block_order': ','.join(design['blocks']), 'version': item.version,
                   'name': item.name, 'description': item.description, 'category': item.category, 'position': item.position}
        super().__init__(*args, initial=initial, **kwargs)
        for role, label in ICON_ROLES:
            self.fields['icon_'+role] = forms.ModelChoiceField(label=label, queryset=TemplateIcon.objects.all(),
                required=False, empty_label='Стандартный значок', initial=design['icons'].get(role))
        for key, _ in BLOCKS:
            values = block_settings(design, key)
            prefix = f'block_{key}_'
            self.fields[prefix+'align'] = forms.ChoiceField(label='Выравнивание текста и кнопок', required=False,
                choices=[('inherit','Как в общих настройках'),('left','По левому краю'),('center','По центру'),('right','По правому краю')], initial=values['align'])
            self.fields[prefix+'iconPosition'] = forms.ChoiceField(label='Положение значков', required=False,
                choices=[('inherit','Как в общих настройках'),('left','Слева'),('right','Справа'),('top','Сверху'),('none','Без значков')], initial=values['iconPosition'])
            self.fields[prefix+'iconSize'] = forms.IntegerField(label='Размер значков', required=False,
                min_value=16, max_value=36, initial=design.get('blockStyles', {}).get(key, {}).get('iconSize'),
                help_text='Пусто — общий размер значков.')
            self.fields[prefix+'icon'] = forms.ModelChoiceField(label='Дополнительный значок блока', required=False,
                queryset=TemplateIcon.objects.all(), empty_label='Без дополнительного значка', initial=values['icon'] or None)

    @property
    def settings_fields(self):
        return [field for field in self if field.name not in ('version','visual_design','block_order','hidden') and not field.name.startswith(('icon_', 'block_'))]

    @property
    def block_fields(self):
        return [{'key': key, 'label': label, 'fields': [self[f'block_{key}_{field}']
                for field in ('align','iconPosition','iconSize','icon')]} for key, label in BLOCKS]

    @property
    def icon_fields(self):
        return [field for field in self if field.name.startswith('icon_')]

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        design = {key: data[key] for key in DEFAULT if key not in ('blocks','icons')}
        design['blocks'] = data['block_order'].split(',')
        design['icons'] = {role: str(data['icon_'+role].pk) for role, _ in ICON_ROLES if data.get('icon_'+role)}
        design['blockStyles'] = {}
        for key, _ in BLOCKS:
            prefix = f'block_{key}_'
            values = {'align': data[prefix+'align'] or 'inherit',
                      'iconPosition': data[prefix+'iconPosition'] or 'inherit'}
            if data[prefix+'iconSize'] is not None:
                values['iconSize'] = data[prefix+'iconSize']
            if data[prefix+'icon']:
                values['icon'] = str(data[prefix+'icon'].pk)
            design['blockStyles'][key] = values
        if data.get('visual_design') is not None:
            visual = data['visual_design']
            validate_design(visual)
            # The visual editor sends the full bounded definition, never HTML/CSS.
            design = visual
        self.design = validate_design(design)
        return data


class IconForm(forms.Form):
    name = forms.CharField(label='Название значка', max_length=80)
    image = forms.FileField(label='Значок SVG', help_text='До 64 КБ. Контуры, фигуры и градиенты; без сценариев, встроенных изображений и внешних ссылок.',
        widget=forms.FileInput(attrs={'accept':'.svg,image/svg+xml'}))

    def clean_image(self):
        return sanitize_svg(self.cleaned_data['image'].read(65537))
