from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User
from django.utils.safestring import mark_safe


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(label='Имя', max_length=150, required=False)
    last_name = forms.CharField(label='Фамилия', max_length=150, required=False)
    email = forms.EmailField(label='Электронная почта')
    consent = forms.BooleanField(label='Даю отдельное согласие на обработку персональных данных',
        help_text=mark_safe('<a href="/legal/processing" target="_blank" rel="noopener">Текст согласия</a> · <a href="/legal/privacy" target="_blank" rel="noopener">Политика обработки данных</a>'))
    terms = forms.BooleanField(label='Принимаю условия публичной оферты',
        help_text=mark_safe('<a href="/legal/offer" target="_blank" rel="noopener">Открыть оферту</a>'))

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.pop('autofocus', None)
        self.fields['first_name'].widget.attrs['autocomplete'] = 'given-name'
        self.fields['last_name'].widget.attrs['autocomplete'] = 'family-name'
        self.fields['email'].widget.attrs.update(autocomplete='email', inputmode='email',
                                                autocapitalize='none', spellcheck='false')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Аккаунт с этим email уже существует.')
        return email


class LoginForm(AuthenticationForm):
    username = forms.EmailField(label='Электронная почта', widget=forms.EmailInput(attrs={
        'autocomplete': 'username', 'inputmode': 'email', 'autocapitalize': 'none', 'spellcheck': 'false'}))

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()


class RegistrationCodeForm(forms.Form):
    code = forms.RegexField(regex=r'\A[0-9]{6}\Z', label='Код из письма',
        error_messages={'invalid': 'Введите шесть цифр из письма.'},
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code',
                                     'maxlength': 6, 'autofocus': True}))
