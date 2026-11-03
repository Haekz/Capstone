"""Avance del alumno por ramo, con sus clases completadas (vista Mi Progreso).

Es lo unico que la plataforma sabe de verdad: cuantas clases y horas lleva en cada ramo. No hay un "porcentaje de
avance" del curriculo (nadie lo registra), asi que la barra solo compara cada ramo con el que mas estudio.
"""

from collections import defaultdict

from .models import Inscripcion


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
