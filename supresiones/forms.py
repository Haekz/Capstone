from django import forms

from apoderados.forms import AccesibleMixin


class EntiendoForm(AccesibleMixin, forms.Form):
    """Primer paso: la persona leyo lo que se elimina y lo que se conserva."""
    entiendo = forms.BooleanField(
        label='Entiendo que eliminar mi cuenta no se puede deshacer y que algunos datos se conservan, '
              'como se explica arriba.',
        error_messages={'required': 'Marca la casilla para continuar.'})


class ConfirmarForm(AccesibleMixin, forms.Form):
    """Segundo paso, tras abrir el enlace del correo."""
    confirmo = forms.BooleanField(label='Sí, quiero que soporte elimine mi cuenta.',
                                  error_messages={'required': 'Marca la casilla para confirmar.'})


class EjecutarForm(AccesibleMixin, forms.Form):
    """Soporte confirma que reviso la evaluacion antes de eliminar (no se puede deshacer)."""
    confirmo = forms.BooleanField(
        label='Revisé la evaluación y corresponde eliminar esta cuenta. Entiendo que no se puede deshacer.',
        error_messages={'required': 'Marca la casilla para eliminar.'})


class RechazarForm(AccesibleMixin, forms.Form):
    motivo = forms.CharField(label='Qué le respondes al usuario', max_length=1000, widget=forms.Textarea(attrs={'rows': 3}),
                             error_messages={'required': 'Explica por qué no se puede eliminar la cuenta.'},
                             help_text='Lo lee en su ticket: dile qué impide eliminarla y qué puede hacer.')
