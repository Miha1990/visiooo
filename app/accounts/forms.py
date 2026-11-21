from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User
from django.utils.safestring import mark_safe


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label='Электронная почта')
    consent = forms.BooleanField(label='Даю отдельное согласие на обработку персональных данных',
        help_text=mark_safe('<a href="/legal/processing" target="_blank" rel="noopener">Текст согласия</a> · <a href="/legal/privacy" target="_blank" rel="noopener">Политика обработки данных</a>'))
    terms = forms.BooleanField(label='Принимаю условия публичной оферты',
        help_text=mark_safe('<a href="/legal/offer" target="_blank" rel="noopener">Открыть оферту</a>'))

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Аккаунт с этим email уже существует.')
        return email


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Электронная почта')

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()
