"""Eliminar una cuenta sin perder las conversaciones reportadas (paso C1e, decidido 03-nov).

Antes, borrar el usuario arrastraba en cascada todas sus conversaciones: tambien las reportadas (la
evidencia) y tambien para la otra persona. Ahora:

- Sin conversaciones reportadas: se borra la cuenta completa, como siempre.
- Con alguna: se borran las demas conversaciones y sus avisos, y la cuenta se **seudonimiza en el mismo
  lugar** ("Cuenta eliminada": sin nombre, correo, RUT, telefono, direccion, nacimiento, genero ni foto, y
  sin poder entrar). Es seudonimizacion, no anonimizacion: los mensajes conservados pueden contener datos
  de la persona. Por eso lo conservado **deja de verse para la otra persona** y queda solo para soporte,
  desde el ticket (Conversacion.objects.visibles(); decidido 02-nov). La fila se conserva solo porque las
  conversaciones reportadas dependen de ella.

Limites: hoy solo se usa con alumnos, el unico borrado que existe. Profesores y apoderados guardan mas
datos propios (documentos, cuenta bancaria): habria que anonimizarlos tambien antes de usarla con ellos.
Los datos de clases y pagos de la cuenta no se tocan: tienen su propia conservacion, por definir con
asesoria legal.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notificaciones.models import Notificacion

from .models import Conversacion

NOMBRE_SUPRIMIDA = 'Cuenta eliminada'


def conversaciones_de(user):
    return Conversacion.objects.filter(Q(cliente=user) | Q(alumno__user=user) | Q(profesor__user=user))


def _seudonimizar(user):
    if user.foto_perfil:
        user.foto_perfil.delete(save=False)  # tambien el archivo, no solo la referencia
    user.username = f'eliminada-{user.pk}'
    user.first_name, user.last_name, user.email = NOMBRE_SUPRIMIDA, '', ''
    user.rut, user.telefono, user.direccion = None, '', ''
    user.fecha_nacimiento, user.genero = None, None
    user.is_active, user.suprimida = False, timezone.now()
    user.set_unusable_password()
    user.save()


def suprimir_cuenta(user):
    """True si se borro por completo; False si quedo seudonimizada porque tiene conversaciones reportadas."""
    with transaction.atomic():
        propias = conversaciones_de(user)
        reportadas = propias.reportadas()
        if not reportadas.exists():
            user.delete()
            return True
        propias.exclude(pk__in=reportadas.values('pk')).delete()
        Notificacion.objects.filter(usuario=user).delete()
        _seudonimizar(user)
        return False
