"""Avance del alumno por ramo, con sus clases completadas (vista Mi Progreso).

Es lo unico que la plataforma sabe de verdad: cuantas clases y horas lleva en cada ramo. No hay un "porcentaje de
avance" del curriculo (nadie lo registra), asi que la barra solo compara cada ramo con el que mas estudio.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Inscripcion

SEMANAS = 5
X_INICIO, X_FIN, Y_BASE, Y_TOPE = 40, 460, 170, 30  # area util del grafico (viewBox 500 x 200)


def horas_por_semana(alumno, hoy=None):
    """Horas de clases completadas en cada una de las ultimas SEMANAS semanas (de lunes a domingo, hora local), de la
    mas antigua a la actual, con las coordenadas ``x`` e ``y`` para dibujarlas. La altura es relativa a la mejor
    semana; sin horas, todo queda en la base."""
    hoy = hoy or timezone.localdate()
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    lunes = [lunes_actual - timedelta(weeks=SEMANAS - 1 - i) for i in range(SEMANAS)]
    desde = timezone.make_aware(datetime.combine(lunes[0], time.min))
    minutos = defaultdict(int)
    completadas = (Inscripcion.objects.filter(alumno=alumno, sesion__fecha_hora_inicio__gte=desde)
                   .completadas().select_related('sesion'))
    for inscripcion in completadas:
        dia = inscripcion.sesion.inicio_local.date()
        minutos[dia - timedelta(days=dia.weekday())] += inscripcion.sesion.duracion_minutos
    horas = [round(minutos[inicio] / 60, 1) for inicio in lunes]
    mayor = max(horas)
    paso = (X_FIN - X_INICIO) / (SEMANAS - 1)
    return [{'desde': inicio, 'horas': h, 'x': round(X_INICIO + paso * i),
             'y': round(Y_BASE - (Y_BASE - Y_TOPE) * h / mayor) if mayor else Y_BASE}
            for i, (inicio, h) in enumerate(zip(lunes, horas))]


def por_ramo(alumno):
    """Lista de {nombre, clases, horas, porcentaje}, del ramo con mas horas al que menos. ``porcentaje`` va de 0 a 100
    respecto del ramo con mas horas (solo sirve para dibujar la barra)."""
    acumulado = defaultdict(lambda: {'clases': 0, 'minutos': 0})
    completadas = Inscripcion.objects.filter(alumno=alumno).completadas().select_related('sesion', 'clase__asignatura')
    for inscripcion in completadas:
        ramo = acumulado[inscripcion.clase.asignatura.nombre]
        ramo['clases'] += 1
        ramo['minutos'] += inscripcion.sesion.duracion_minutos
    mayor = max((ramo['minutos'] for ramo in acumulado.values()), default=0)
    ramos = [{'nombre': nombre, 'clases': ramo['clases'], 'horas': round(ramo['minutos'] / 60, 1),
              'porcentaje': round(100 * ramo['minutos'] / mayor) if mayor else 0}
             for nombre, ramo in acumulado.items()]
    return sorted(ramos, key=lambda ramo: (-ramo['horas'], ramo['nombre']))
