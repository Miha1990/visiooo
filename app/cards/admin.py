from django.contrib import admin
from .models import Card, CardRevision, PhysicalCard, PhysicalCardEvent
from .models import CardTemplate, TemplateIcon
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html


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
    change_list_template = 'admin/cards/physicalcard/change_list.html'
    list_display = ('label', 'workspace', 'card', 'activation_state', 'permanent_link', 'enabled', 'blocked')
    list_filter = ('blocked', 'enabled')
    list_select_related = ('workspace', 'card')
    search_fields = ('label', 'public_id', 'workspace__owner__email')
    readonly_fields = ('id', 'public_id', 'workspace', 'card', 'label', 'enabled', 'version', 'created_at', 'updated_at', 'permanent_link')

    @admin.display(description='Активация')
    def activation_state(self, obj):
        return 'Ожидает клиента' if obj.workspace_id is None else 'Активирована'

    @admin.display(description='Ссылка NFC / QR')
    def permanent_link(self, obj):
        from .physical import physical_url
        url = physical_url(obj)
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, url)

    def add_view(self, request, form_url='', extra_context=None):
        from .physical import PhysicalIssueForm, issue_physical, physical_url
        from accounts.views import redirect303
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = PhysicalIssueForm(request.POST if request.method == 'POST' else None)
        if request.method == 'POST' and form.is_valid():
            with transaction.atomic():
                items = issue_physical(request.user, form.cleaned_data['label'], form.cleaned_data['count'])
                for item in items:
                    self.log_addition(request, item, 'Выпущена заготовка NFC / QR для активации клиентом.')
            self.message_user(request, f'Выпущено карт: {len(items)}. Ссылки для записи NFC и QR находятся в списке ниже.')
            return redirect303(reverse('admin:cards_physicalcard_add'))
        page = Paginator(PhysicalCard.objects.filter(workspace__isnull=True).order_by('-created_at', 'pk'), 50).get_page(request.GET.get('page'))
        context = {**self.admin_site.each_context(request), 'opts': self.model._meta,
                   'title': 'Выпустить ссылки для NFC / QR-карт', 'form': form, 'media': self.media + form.media,
                   'has_view_permission': self.has_view_or_change_permission(request), 'page': page,
                   'stock': [{'item': item, 'url': physical_url(item)} for item in page], **(extra_context or {})}
        return TemplateResponse(request, 'admin/cards/physicalcard/issue.html', context,
                                status=422 if request.method == 'POST' else 200)

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
