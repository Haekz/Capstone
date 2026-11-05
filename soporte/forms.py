from django import forms

from apoderados.forms import AccesibleMixin

from .models import AgenteSoporte, Ticket


class ReporteForm(AccesibleMixin, forms.Form):
    """Ticket que abre un usuario. ``categorias``: las que puede abrir (permisos.categorias_que_reporta).
    ``estudiantes``: los del apoderado, para indicar de quien se trata (D18)."""
    categoria = forms.ChoiceField(label='¿Sobre qué es?')
    titulo = forms.CharField(label='Asunto', max_length=120)
    descripcion = forms.CharField(label='Cuéntanos qué pasó', max_length=2000, widget=forms.Textarea,
                                  help_text='No escribas contraseñas ni datos de tarjetas.')

    def __init__(self, *args, categorias, estudiantes=None, **kwargs):
        super().__init__(*args, **kwargs)
        nombres = dict(Ticket.CATEGORIAS)
        self.fields['categoria'].choices = [(c, nombres[c]) for c in categorias]
        if estudiantes:
            self.fields['estudiante'] = forms.ModelChoiceField(
                queryset=estudiantes, required=False, label='¿De qué estudiante se trata?',
                empty_label='De ninguno en particular',
                error_messages={'invalid_choice': 'Elige uno de tus estudiantes.'})
            self.fields['estudiante'].label_from_instance = lambda alumno: alumno.user.first_name


class MensajeForm(AccesibleMixin, forms.Form):
    """El usuario contesta en su ticket."""
    texto = forms.CharField(label='Tu respuesta', max_length=2000, widget=forms.Textarea(attrs={'rows': 4}),
                            help_text='No escribas contraseñas ni datos de tarjetas.')


class RespuestaForm(MensajeForm):
    """El agente responde y, si ya esta resuelto, cierra el ticket con la misma respuesta."""
    cerrar = forms.BooleanField(label='Cerrar el ticket con esta respuesta', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['texto'].label = 'Respuesta al usuario'
        self.fields['texto'].help_text = 'El usuario la lee en LBWUS; el correo solo le avisa que respondiste.'


class RespuestaContactoForm(MensajeForm):
    """El agente responde a un visitante de Contactanos (H14). Siempre cierra: el visitante no
    tiene cuenta para contestar, si necesita algo mas vuelve a escribir. Sin texto, solo si lo
    cierra sin responder (spam o repetido)."""
    sin_respuesta = forms.BooleanField(label='Cerrar sin responder (spam o mensaje repetido)', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        texto = self.fields['texto']
        texto.required = False
        texto.label = 'Respuesta al visitante'
        texto.help_text = ('Le llega tal cual a su correo y se cierra el ticket. No tiene cuenta: no pidas '
                           'su contraseña, RUT ni datos de pago.')

    def clean(self):
        datos = super().clean()
        if datos.get('sin_respuesta') == bool(datos.get('texto')):
            raise forms.ValidationError('Escribe una respuesta o marca "Cerrar sin responder" (solo una de las dos).')
        datos['cerrar'] = True
        return datos


class ReasignarForm(forms.Form):
    agente = forms.ModelChoiceField(
        queryset=AgenteSoporte.objects.all(),
        error_messages={'required': 'Elige un agente.', 'invalid_choice': 'Ese agente no existe.'},
    )


class EscalarForm(AccesibleMixin, forms.Form):
    """Motivo obligatorio para escalar un caso grave (al lider o a un administrador)."""
    motivo = forms.CharField(label='¿Por qué lo escalas?', max_length=1000, widget=forms.Textarea(attrs={'rows': 4}),
                             help_text='Por ejemplo: amenaza legal, posible delito, datos de un menor expuestos.',
                             error_messages={'required': 'Escribe por qué lo escalas.'})


class IndicacionForm(AccesibleMixin, forms.Form):
    """Lo que el administrador decide en un caso escalado; soporte lo ejecuta."""
    indicacion = forms.CharField(label='Tu indicación para soporte', max_length=1000,
                                 widget=forms.Textarea(attrs={'rows': 3}),
                                 error_messages={'required': 'Escribe tu indicación para soporte.'})
