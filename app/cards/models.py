import secrets
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from workspaces.models import Workspace


def public_id():
    return secrets.token_urlsafe(24)


def empty_content():
    return {'schemaVersion': 1, 'name': 'Новая визитка', 'template': 'classic', 'accent': '#2457DB', 'links': []}


class CardTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('Название', max_length=100)
    description = models.CharField('Описание', max_length=300, blank=True)
    category = models.CharField('Категория', max_length=60, blank=True)
    draft = models.JSONField('Оформление черновика', default=dict)
    version = models.PositiveIntegerField('Версия черновика', default=1)
    published = models.JSONField('Опубликованное оформление', default=dict)
    published_version = models.PositiveIntegerField('Редакция в каталоге', default=0)
    status = models.CharField('Состояние', max_length=12, default='draft', choices=[
        ('draft', 'Черновик'), ('published', 'В каталоге'), ('archived', 'В архиве')])
    position = models.PositiveIntegerField('Порядок в каталоге', default=0)
    updated_at = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        verbose_name = 'шаблон визитки'
        verbose_name_plural = 'Шаблоны визиток'
        ordering = ['position', 'name']

    def __str__(self):
        return self.name


class TemplateIcon(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('Название', max_length=80)
    svg = models.TextField('Проверенный значок SVG', editable=False)
    created_at = models.DateTimeField('Добавлен', auto_now_add=True)
    owner = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.CASCADE,
                              verbose_name='Владелец', related_name='card_icons')

    class Meta:
        verbose_name = 'значок шаблона'
        verbose_name_plural = 'Значки шаблонов'
        ordering = ['name']

    def __str__(self):
        return self.name


class TemplatePhoto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('Название', max_length=100)
    image = models.BinaryField('Изображение WebP', editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'фотография шаблона'
        verbose_name_plural = 'Фотографии шаблонов'


class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    public_id = models.CharField(max_length=40, unique=True, default=public_id, editable=False, verbose_name='Публичный идентификатор')
    draft = models.JSONField(default=empty_content, verbose_name='Черновик')
    draft_version = models.PositiveIntegerField(default=1, verbose_name='Версия черновика')
    published_revision = models.ForeignKey('CardRevision', on_delete=models.SET_NULL, null=True,
                                           blank=True, related_name='+', verbose_name='Опубликованная версия')
    status = models.CharField(max_length=12, choices=[('draft', 'Черновик'), ('published', 'Опубликовано'),
                                                    ('deleted', 'Удалено')], default='draft', verbose_name='Статус')
    blocked = models.BooleanField(default=False, verbose_name='Заблокирована')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')

    class Meta:
        verbose_name = 'визитка'
        verbose_name_plural = 'Визитки'
        indexes = [models.Index(fields=['workspace', '-updated_at'])]

    @property
    def has_changes(self):
        return self.published_revision_id and self.draft != self.published_revision.content

    def __str__(self):
        return self.draft.get('name', 'Визитка')


class CardDailyViews(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='daily_views', verbose_name='Визитка')
    day = models.DateField('День по московскому времени')
    views = models.PositiveBigIntegerField('Просмотры', default=0)

    class Meta:
        verbose_name = 'просмотры визитки за день'
        verbose_name_plural = 'Просмотры визиток по дням'
        constraints = [models.UniqueConstraint(fields=['card', 'day'], name='unique_card_views_day')]


class CardRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='revisions', verbose_name='Визитка')
    schema_version = models.PositiveSmallIntegerField(default=1, verbose_name='Версия формата')
    content = models.JSONField(verbose_name='Содержимое')
    publication_conditions = models.TextField(blank=True, verbose_name='Условия публикации')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Опубликованные версии нельзя изменять.')
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'версия визитки'
        verbose_name_plural = 'Версии визиток'

    def __str__(self):
        return f'Версия визитки {self.pk}'


class Asset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    kind = models.CharField(max_length=8, default='image', choices=[('image','Изображение'),('pdf','PDF-файл')], verbose_name='Тип файла')
    object_key = models.CharField(max_length=240, unique=True, editable=False, verbose_name='Путь в хранилище')
    bytes = models.PositiveIntegerField(verbose_name='Размер в байтах')
    width = models.PositiveIntegerField(verbose_name='Ширина')
    height = models.PositiveIntegerField(verbose_name='Высота')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')

    class Meta:
        verbose_name = 'изображение'
        verbose_name_plural = 'Изображения'


class PhysicalCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, verbose_name='Идентификатор')
    public_id = models.CharField(max_length=40, unique=True, default=public_id, editable=False, verbose_name='Публичный идентификатор')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, verbose_name='Личный кабинет')
    card = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Электронная визитка')
    label = models.CharField(max_length=100, verbose_name='Название')
    enabled = models.BooleanField(default=True, verbose_name='Включена')
    blocked = models.BooleanField(default=False, verbose_name='Заблокирована')
    version = models.PositiveIntegerField(default=1, verbose_name='Версия')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')

    def __str__(self):
        return self.label

    class Meta:
        verbose_name = 'физическая визитка'
        verbose_name_plural = 'Физические визитки'


class PhysicalCardEvent(models.Model):
    physical_card = models.ForeignKey(PhysicalCard, on_delete=models.CASCADE, related_name='events', verbose_name='Физическая визитка')
    actor = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, verbose_name='Пользователь')
    action = models.CharField(max_length=20, verbose_name='Действие', choices=[
        ('created', 'Создана'), ('bound', 'Привязана'), ('disabled', 'Отключена')])
    target_card = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, verbose_name='Электронная визитка')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата события')

    class Meta:
        verbose_name = 'событие физической визитки'
        verbose_name_plural = 'События физических визиток'

    def __str__(self):
        return f'{self.get_action_display()} — {self.physical_card}'


class CardBlockSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    carousel_limit = models.PositiveSmallIntegerField(default=10, verbose_name='Максимум фото в карусели',
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text='От 1 до 100. Уменьшение лимита не удаляет уже загруженные фото.')

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def __str__(self):
        return 'Лимиты блоков визитки'

    class Meta:
        verbose_name = 'настройки блоков визитки'
        verbose_name_plural = 'Настройки блоков визитки'
