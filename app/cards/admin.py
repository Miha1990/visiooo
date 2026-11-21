from django.contrib import admin
from .models import Card, CardRevision, PhysicalCard, PhysicalCardEvent


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
