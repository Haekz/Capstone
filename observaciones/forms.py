from django import forms

from mensajes.filtro import exigir_sin_contacto

from .models import Observacion


class ObservacionForm(forms.Form):
    texto = forms.CharField(label='Observación', min_length=10, max_length=Observacion.MAXIMO, strip=True,
                            widget=forms.Textarea(attrs={'rows': 3, 'maxlength': Observacion.MAXIMO}),
                            error_messages={'min_length': 'Escribe al menos 10 caracteres.',
                                            'required': 'Escribe la observación.'})

    def clean_texto(self):
        texto = self.cleaned_data['texto']
        exigir_sin_contacto(texto)  # mismo filtro que el chat: nada de pasarse telefonos o redes por aqui
        return texto
