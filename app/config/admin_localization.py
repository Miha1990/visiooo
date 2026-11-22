from django.apps import apps
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.models import Group


def permission_label(permission):
    model = permission.content_type.model_class()
    model_label = model._meta.verbose_name if model else permission.content_type.model
    try:
        app_label = apps.get_app_config(permission.content_type.app_label).verbose_name
    except LookupError:
        app_label = 'Архивные разрешения'
    action = permission.codename.split('_', 1)[0]
    action_label = {'add': 'Добавление', 'change': 'Изменение', 'delete': 'Удаление', 'view': 'Просмотр'}.get(action)
    return f'{app_label} — {model_label}: {action_label or permission.name}'


class RussianPermissionLabelsMixin:
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if field is not None and db_field.name in ('user_permissions', 'permissions'):
            field.label_from_instance = permission_label
        return field


admin.site.site_header = 'Управление сервисом «Визитка»'
admin.site.site_title = 'Администрирование — Визитка'
admin.site.index_title = 'Разделы управления'


admin.site.unregister(Group)


@admin.register(Group)
class RussianGroupAdmin(RussianPermissionLabelsMixin, GroupAdmin):
    pass
