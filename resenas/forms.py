from django import forms

from .models import ModeracionResena, ReporteResena, Resena

PUNTAJES = [(n, f'{n} estrella{"s" if n > 1 else ""}') for n in range(1, 6)]


class ResenaForm(forms.ModelForm):
    puntaje = forms.TypedChoiceField(choices=PUNTAJES, coerce=int, widget=forms.RadioSelect,
                                     label='Puntaje')

    class Meta:
        model = Resena
        fields = ['puntaje', 'comentario']
        widgets = {'comentario': forms.Textarea(attrs={'rows': 5, 'maxlength': 1000})}
        labels = {'comentario': 'Comentario (opcional)'}
        help_texts = {'comentario': 'Máximo 1.000 caracteres. No incluyas datos personales.'}


class ReporteForm(forms.ModelForm):
    class Meta:
        model = ReporteResena
        fields = ['motivo', 'detalle']


class ModeracionForm(forms.ModelForm):
    class Meta:
        model = ModeracionResena
        fields = ['accion', 'criterio', 'observacion']

    def clean(self):
        datos = super().clean()
        if datos.get('accion') == ModeracionResena.OCULTAR and not datos.get('criterio'):
            self.add_error('criterio', 'Para ocultar una reseña indica qué criterio incumple.')
        return datos
