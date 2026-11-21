from urllib.parse import urlsplit
from django import forms
from .models import Payment


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
