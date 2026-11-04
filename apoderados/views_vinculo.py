"""Un segundo apoderado se vincula a un menor que ya esta registrado (decidido 02-nov, opcion A).

Lo pide con el RUT del estudiante y el documento que acredita el vinculo; soporte lo verifica igual que
cualquier otro. No se le muestra nada del estudiante hasta entonces (Vinculo.nombre_visible).
"""

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache

from alumnos.decorators import apoderado_required
from alumnos.roles import APODERADO

from .correo import avisar_segundo_apoderado
from .forms import VincularEstudianteForm
from .views import _apoderado_en_sesion, _formulario, redirigir_si_no_verificado


@never_cache
@apoderado_required
def vincular_estudiante(request):
    apoderado = _apoderado_en_sesion(request)
    sin_verificar = redirigir_si_no_verificado(request, apoderado)
    if sin_verificar:
        return sin_verificar
    form = VincularEstudianteForm(request.POST or None, request.FILES or None, apoderado=apoderado)
    if request.method == 'POST' and form.is_valid():
        avisar_segundo_apoderado(form.save())
        messages.success(request, 'Recibimos tu solicitud. Nuestro equipo de soporte revisará el documento que '
                                  'adjuntaste para verificar el vínculo.')
        return redirect(APODERADO.ruta_portal)
    return _formulario(
        request, form, titulo='Vincularme a un estudiante ya registrado', subtitulo='Datos del estudiante',
        boton='Pedir el vínculo', volver_url=reverse(APODERADO.ruta_portal),
        intro=('Si otra persona ya registró al estudiante, escribe su RUT y adjunta el documento que acredita tu '
               'vínculo. Hasta que nuestro equipo lo verifique no verás datos del estudiante ni podrás actuar por él. '
               'Los apoderados que ya están vinculados, y el estudiante si tiene 14 años o más y correo propio, '
               'recibirán un aviso, sin tus datos.'),
    )
