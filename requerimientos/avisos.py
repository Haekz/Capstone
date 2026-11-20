"""Recordatorio a los lideres de soporte: requerimientos de autoridad abiertos cuyo plazo se acerca o ya paso.

Pensado para un cron diario en Railway: python manage.py avisar_requerimientos_por_vencer
Avisa cada dia habil desde AVISO_ANTES dias habiles antes del plazo, y todos los dias mientras siga atrasado.
Un solo correo por lider, solo con cantidades: autoridad y referencia se ven en LBWUS.
"""

from alumnos.correo import enviar
from soporte.correo import lideres
from soporte.plazos import dias_habiles_entre

from .models import Requerimiento

AVISO_ANTES = 3  # dias habiles antes del plazo en que empieza el recordatorio
PLANTILLA = 'requerimientos/correo_por_vencer.txt'


def contar(hoy):
    """(proximos, atrasados): abiertos con plazo que vence en AVISO_ANTES dias habiles o menos, y ya vencidos."""
    con_plazo = Requerimiento.objects.filter(estado__in=Requerimiento.ABIERTOS, vence__isnull=False)
    atrasados = con_plazo.filter(vence__lt=hoy).count()
    proximos = sum(dias_habiles_entre(hoy, vence) <= AVISO_ANTES
                   for vence in con_plazo.filter(vence__gte=hoy).values_list('vence', flat=True))
    return proximos, atrasados


def avisar(hoy):
    """Avisa a cada lider si hay requerimientos por vencer o atrasados. Devuelve cuantos eran."""
    proximos, atrasados = contar(hoy)
    if proximos or atrasados:
        for lider in lideres():
            enviar('Requerimientos de autoridad por vencer', PLANTILLA,
                   {'nombre': lider.nombre, 'proximos': proximos, 'atrasados': atrasados, 'antes': AVISO_ANTES},
                   lider.user.email)
    return proximos + atrasados
