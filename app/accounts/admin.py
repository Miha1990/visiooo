from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User, LegalAcceptance
from config.admin_localization import RussianPermissionLabelsMixin


class AccountCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email',)


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class AccountAdmin(RussianPermissionLabelsMixin, UserAdmin):
    add_form = AccountCreationForm
    form = AccountChangeForm
    ordering = ('email',)
    list_display = ('email', 'email_verified_at', 'is_staff', 'is_active')
    search_fields = ('email',)
    fieldsets = ((None, {'fields': ('email', 'password')}),
                 ('Доступ', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                 ('Даты', {'fields': ('email_verified_at', 'last_login', 'date_joined')}))
    add_fieldsets = ((None, {'fields': ('email', 'password1', 'password2')}),)


@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'document', 'version', 'accepted_at')
    list_filter = ('document', 'version')
    search_fields = ('user__email',)
    readonly_fields = tuple(field.name for field in LegalAcceptance._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
