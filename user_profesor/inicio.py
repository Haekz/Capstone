"""Inicio del panel del profesor: lo de HOY con datos reales (hora de Chile).

Antes: "Clases de Hoy" eran sus primeras 6 materias (sin mirar la fecha), el dinero sumaba inscripciones
de cualquier dia y las disponibles eran 8 menos esa lista. Ahora cada numero sale de la agenda real.
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

from alumnos import paquetes
from alumnos.models import Inscripcion, SesionClase
from alumnos.utils import formato_clp


def _hoy():
    """Inicio y fin del dia de hoy en Chile."""
    inicio = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    return inicio, inicio + timedelta(days=1)


def contexto(profesor):
    desde, hasta = _hoy()
    de_hoy = Inscripcion.objects.filter(clase__profesor=profesor, sesion__fecha_hora_inicio__gte=desde,
                                        sesion__fecha_hora_inicio__lt=hasta)
    reservadas = (de_hoy.filter(estado__in=Inscripcion.ESTADOS_ACTIVOS)
                  .exclude(sesion__estado=SesionClase.ESTADO_CANCELADA)
                  .select_related('sesion', 'clase__asignatura', 'alumno__user')
                  .order_by('sesion__fecha_hora_inicio'))
    # Lo ganado hoy, con la misma regla que su saldo (saldos.py): clases ya dictadas o canceladas tarde.
    ganado = sum(paquetes.pago_profesor(paquetes.valor_clase(i))
                 for i in de_hoy.pagables().select_related('paquete', 'clase'))
    # Bloques que quedan libres hoy. La agenda crea un bloque por materia a la misma hora: se cuentan horas.
    libres = set(SesionClase.objects.disponibles().filter(clase__profesor=profesor, fecha_hora_inicio__lt=hasta)
                 .values_list('fecha_hora_inicio', flat=True))
    return {
        'clases_hoy': [{
            'inicio': i.sesion.fecha_hora_inicio,
            'fin': i.sesion.fecha_hora_fin,
            'nombre_curso': i.clase.asignatura.nombre,
            'modalidad': i.clase.get_modalidad_display(),
            'alumno': i.alumno.user.first_name,
        } for i in reservadas],
        'dinero_hoy': formato_clp(ganado),
        'clases_disponibles': len(libres),
    }
