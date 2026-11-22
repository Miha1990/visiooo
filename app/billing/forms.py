from urllib.parse import urlsplit
from django import forms
from .models import Payment, PromoCode, AccessGrant
from accounts.models import User


class PaymentAdminForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = '__all__'

    def clean_receipt_url(self):
        url = self.cleaned_data.get('receipt_url', '')
        if url:
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname != 'lknpd.nalog.ru' or parsed.username or parsed.password or parsed.port not in (None, 443):
                raise forms.ValidationError('Укажите HTTPS-ссылку чека из «Мой налог» на lknpd.nalog.ru.')
        return url


class PromoCodeForm(forms.Form):
    code = forms.CharField(label='Промокод', max_length=40,
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'characters', 'placeholder': 'Введите промокод'}))


class PromoAdminForm(forms.ModelForm):
    class Meta:
        model = PromoCode
        fields = '__all__'

    def clean_code(self):
        return self.cleaned_data['code'].strip().upper()

    def clean_email(self):
        return self.cleaned_data.get('email', '').strip().lower()

    def clean(self):
        data = super().clean()
        if data.get('starts_at') and data.get('expires_at') and data['expires_at'] <= data['starts_at']:
            self.add_error('expires_at', 'Окончание должно быть позже начала.')
        return data


class AccessGrantAdminForm(forms.ModelForm):
    class Meta:
        model = AccessGrant
        fields = ('user', 'days', 'permanent', 'note')

    def clean_user(self):
        user = self.cleaned_data['user']
        if not user.is_active or not User.objects.filter(pk=user.pk, workspace__isnull=False).exists():
            raise forms.ValidationError('Выберите действующий зарегистрированный аккаунт с кабинетом.')
        return user
