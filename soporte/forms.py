from django import forms

from apoderados.forms import AccesibleMixin

from .models import AgenteSoporte, Ticket


class ReporteForm(AccesibleMixin, forms.Form):
    """Ticket que abre un usuario. ``categorias``: las que puede abrir (permisos.categorias_que_reporta)."""
    categoria = forms.ChoiceField(label='¿Sobre qué es?')
    titulo = forms.CharField(label='Asunto', max_length=120)
    descripcion = forms.CharField(label='Cuéntanos qué pasó', max_length=2000, widget=forms.Textarea,
                                  help_text='No escribas contraseñas ni datos de tarjetas.')

    def __init__(self, *args, categorias, **kwargs):
        super().__init__(*args, **kwargs)
        nombres = dict(Ticket.CATEGORIAS)
        self.fields['categoria'].choices = [(c, nombres[c]) for c in categorias]


class ReasignarForm(forms.Form):
    agente = forms.ModelChoiceField(
        queryset=AgenteSoporte.objects.all(),
        error_messages={'required': 'Elige un agente.', 'invalid_choice': 'Ese agente no existe.'},
    )
