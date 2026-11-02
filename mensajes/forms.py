from django import forms

from apoderados.forms import AccesibleMixin


class ReportarConversacionForm(AccesibleMixin, forms.Form):
    descripcion = forms.CharField(
        label='Cuéntanos qué pasó', max_length=2000, widget=forms.Textarea,
        help_text='Explícalo con tus palabras. No escribas contraseñas ni datos de tarjetas.')
