from django import forms
from cards.models import Card
from .validation import normalize_hostname


class DomainForm(forms.Form):
    hostname = forms.CharField(label='Ваш домен', max_length=253,
        widget=forms.TextInput(attrs={'placeholder': 'card.example.ru', 'autocapitalize': 'none'}))
    card = forms.ModelChoiceField(label='Какую визитку открывать на домене', queryset=Card.objects.none())

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['card'].queryset = Card.objects.filter(workspace=workspace).exclude(status='deleted')

    def clean_hostname(self):
        return normalize_hostname(self.cleaned_data['hostname'])


class DomainTargetForm(forms.Form):
    card = forms.ModelChoiceField(label='Визитка на главной странице домена', queryset=Card.objects.none())
    generation = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['card'].queryset = Card.objects.filter(workspace=workspace).exclude(status='deleted')
