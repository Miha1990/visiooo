from django.contrib import admin
from .models import DomainBinding, DomainAudit


@admin.register(DomainBinding)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'workspace', 'root_card', 'state', 'blocked', 'certificate_expires_at')
    readonly_fields = ('id', 'hostname', 'workspace', 'root_card', 'state', 'verified_at', 'checked_at',
        'certificate_expires_at', 'error', 'requested_at', 'lease_until', 'generation', 'created_at')
    exclude = ('verification_nonce', 'verification_token_hash')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        DomainAudit.objects.create(workspace=obj.workspace, actor=request.user, hostname=obj.hostname,
                                   action='admin_block' if obj.blocked else 'admin_unblock')


@admin.register(DomainAudit)
class AuditAdmin(admin.ModelAdmin):
    list_display = ('hostname', 'workspace', 'actor', 'action', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
