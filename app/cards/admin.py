from django.contrib import admin
from .models import Card, CardRevision, PhysicalCard, PhysicalCardEvent
from .models import CardTemplate, TemplateIcon
from django.shortcuts import redirect


@admin.register(CardTemplate)
class TemplateAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return redirect('/control/templates')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return redirect('/control/templates/' + object_id)


@admin.register(TemplateIcon)
class IconAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.has_perm('cards.change_cardtemplate'):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return redirect('/control/icons')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'status', 'blocked', 'updated_at')
    list_filter = ('blocked', 'status')
    fields = ('id', 'workspace', 'public_id', 'status', 'blocked')
    readonly_fields = ('id', 'workspace', 'public_id', 'status')

    def has_add_permission(self, request):
        return False


@admin.register(CardRevision)
class RevisionAdmin(admin.ModelAdmin):
    readonly_fields = ('id', 'card', 'content', 'schema_version', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PhysicalCard)
class PhysicalCardAdmin(admin.ModelAdmin):
    list_display = ('label', 'workspace', 'card', 'enabled', 'blocked')
    list_filter = ('blocked', 'enabled')
    readonly_fields = ('id', 'public_id', 'workspace', 'card', 'label', 'enabled', 'version', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PhysicalCardEvent)
class PhysicalCardEventAdmin(admin.ModelAdmin):
    list_display = ('physical_card', 'actor', 'action', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import CardBlockSettings

@admin.register(CardBlockSettings)
class BlockSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not CardBlockSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
