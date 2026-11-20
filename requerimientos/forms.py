from django import forms

from apoderados.forms import AccesibleMixin

AVISO_SIN_DATOS = 'No copies nombres, RUT ni contenido: describe el tipo de datos y refiérete a las personas por número de ticket.'
FALTA = {'required': 'Marca la casilla para continuar.'}


def _texto(label, ayuda=None, filas=3, largo=1000):
    return forms.CharField(label=label, max_length=largo, widget=forms.Textarea(attrs={'rows': filas}), help_text=ayuda)


class RegistrarForm(AccesibleMixin, forms.Form):
    autoridad = forms.CharField(label='Autoridad que lo pide', max_length=150,
                                help_text='Por ejemplo: Fiscalía Local de Providencia, Tribunal de Familia.')
    referencia = forms.CharField(label='Oficio, causa o RIT', max_length=100)
    recibido = forms.DateField(label='Recibido el', widget=forms.DateInput(attrs={'type': 'date'}))
    vence = forms.DateField(label='Plazo que fija la autoridad', required=False, widget=forms.DateInput(attrs={'type': 'date'}),
                            help_text='Déjalo vacío si no fija plazo.')
    alcance = _texto('Qué datos pide', AVISO_SIN_DATOS)


class VerificarForm(AccesibleMixin, forms.Form):
    """Antes de entregar nada: los tres controles y como se verificaron. Las casillas no se guardan (prefijo ok_):
    solo se puede verificar si estan todas marcadas."""
    ok_identidad = forms.BooleanField(
        label='Confirmé que el requerimiento viene de la autoridad que dice ser (revisé el oficio y la vía de contacto).',
        error_messages=FALTA)
    ok_base_legal = forms.BooleanField(
        label='La autoridad es competente y indica en qué se funda para pedir los datos.', error_messages=FALTA)
    ok_alcance = forms.BooleanField(label='Entregaré solo lo que pide, y solo lo necesario.', error_messages=FALTA)
    verificacion = _texto('Cómo lo verificaste', 'Por ejemplo: oficio recibido por correo institucional y confirmado por teléfono con la secretaría.')


class RechazarForm(AccesibleMixin, forms.Form):
    resolucion = _texto('Por qué se rechaza', 'No se pudo verificar, no es competente o pide más de lo necesario.')


class EntregarForm(AccesibleMixin, forms.Form):
    datos = _texto('Qué se entregó', AVISO_SIN_DATOS)
    medio = forms.CharField(label='Por qué medio', max_length=100, help_text='Por ejemplo: oficio de respuesta, correo institucional.')
    destinatario = forms.CharField(label='A quién', max_length=150, help_text='Funcionario o unidad que lo recibió y cómo se confirmó.')


class CerrarForm(AccesibleMixin, forms.Form):
    resolucion = _texto('Resumen de lo que se hizo', 'Se cierra el requerimiento. No se puede volver a abrir.')
