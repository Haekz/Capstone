from django import forms

from .models import AgenteSoporte


class ReasignarForm(forms.Form):
    agente = forms.ModelChoiceField(
        queryset=AgenteSoporte.objects.all(),
        error_messages={'required': 'Elige un agente.', 'invalid_choice': 'Ese agente no existe.'},
    )
