"""Personas que usan LBWUS cada dia (H8), sin guardar quien.

Django ya anota en cada usuario su ultimo inicio de sesion (last_login). Los
usuarios de un rol cuyo ultimo inicio fue hoy son las personas distintas que
entraron hoy: al iniciar sesion se cuentan y se guarda solo el numero del dia.
Durante el dia ese numero solo sube; los dias pasados ya no cambian.
Cuenta inicios de sesion: quien vuelve con la sesion abierta no suma.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.utils import timezone

from .models import IngresoDiario


def registrar(sender, request, user, **kwargs):
    """Receptor de user_logged_in (tambien con Google: allauth usa el mismo login)."""
    hoy = timezone.localdate()
    personas = (get_user_model().objects.filter(rol=user.rol)
                .filter(Q(last_login__date=hoy) | Q(pk=user.pk))  # no depende del orden de los receptores
                .count())
    fila, _ = IngresoDiario.objects.get_or_create(fecha=hoy, rol=user.rol)
    # Solo sube: si dos ingresos se cruzan, no gana el conteo mas bajo.
    IngresoDiario.objects.filter(pk=fila.pk, personas__lt=personas).update(personas=personas)


def de_hoy():
    """{'total': n, 'por_rol': [(etiqueta, n), ...]} de las personas que entraron hoy."""
    filas = IngresoDiario.objects.filter(fecha=timezone.localdate(), personas__gt=0)
    return {
        'total': filas.aggregate(total=Sum('personas'))['total'] or 0,
        'por_rol': [(fila.get_rol_display(), fila.personas) for fila in filas],
    }
