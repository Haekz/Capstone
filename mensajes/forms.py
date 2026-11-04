from django import forms

from apoderados.forms import AccesibleMixin

from .models import DecisionRetencion


class ConservarForm(AccesibleMixin, forms.Form):
    """Lo que el lider registra al conservar una conversacion reportada como retencion excepcional (C1f)."""
    motivo = forms.ChoiceField(label='Motivo', choices=DecisionRetencion.MOTIVOS)
    alcance = forms.CharField(label='Datos y mensajes que se conservan', max_length=1000, widget=forms.Textarea(attrs={'rows': 3}),
                              help_text='Qué se conserva y por qué es necesario conservarlo.')
    fundamento = forms.CharField(label='Fundamento', max_length=1000, widget=forms.Textarea(attrs={'rows': 3}),
                                 help_text='La necesidad concreta: reclamo, requerimiento o investigación.')
    termino = forms.CharField(label='Condición de término', max_length=1000, widget=forms.Textarea(attrs={'rows': 2}),
                              help_text='Cuándo deja de ser necesaria. Se vuelve a revisar a los 6 meses.')


class ReportarConversacionForm(AccesibleMixin, forms.Form):
    descripcion = forms.CharField(
        label='Cuéntanos qué pasó', max_length=2000, widget=forms.Textarea,
        help_text='Explícalo con tus palabras. No escribas contraseñas ni datos de tarjetas.')
