"""El profesor deja o corrige su observacion sobre una clase que ya hizo. Vuelve a su panel con un mensaje."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from alumnos.decorators import profesor_required
from alumnos.models import Inscripcion, Profesor

from .forms import ObservacionForm
from .models import Observacion


@require_POST
@profesor_required
def guardar(request, id_inscripcion):
    profesor = get_object_or_404(Profesor, id_profesor=request.session.get('profesor_id'))
    # Solo clases ya realizadas y propias: cualquier otra es 404, igual que si no existiera.
    inscripcion = get_object_or_404(Inscripcion.objects.completadas().filter(clase__profesor=profesor),
                                    pk=id_inscripcion)
    form = ObservacionForm(request.POST)
    if form.is_valid():
        Observacion.objects.update_or_create(inscripcion=inscripcion, defaults={'texto': form.cleaned_data['texto']})
        messages.success(request, 'Observación guardada.')
    else:
        messages.error(request, form.errors['texto'][0])
    return redirect('panel_profesor')
