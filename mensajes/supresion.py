"""Eliminar una cuenta sin perder las conversaciones reportadas (paso C1e, decidido 03-nov) ni su historial
de pagos y clases (S1, decidido 02-nov).

Antes, borrar el usuario arrastraba en cascada todas sus conversaciones: tambien las reportadas (la
evidencia) y tambien para la otra persona. Y tambien sus paquetes pagados y sus clases: se perdia el
registro del pago y al profesor le bajaban las ganancias hacia atras. Ahora:

- Sin conversaciones retenidas (mensajes/revision.py: reportadas, salvo las que el lider libero) ni historial
  de pagos o clases: se borra la cuenta completa, como siempre.
- Con alguno de los dos: se borran las demas conversaciones y sus avisos, y la cuenta se **seudonimiza en el
  mismo lugar** ("Cuenta eliminada": sin nombre, correo, RUT, telefono, direccion, nacimiento, genero ni foto, y
  sin poder entrar). Es seudonimizacion, no anonimizacion: los mensajes conservados pueden contener datos
  de la persona. Por eso lo conservado **deja de verse para la otra persona** y queda solo para soporte,
  desde el ticket (Conversacion.objects.visibles(); decidido 02-nov). La fila se conserva porque las
  conversaciones reportadas, los paquetes y las clases dependen de ella.

Alumnos, profesores y apoderados pasan por aqui. Lo que depende del rol (que historial se conserva y que datos
propios se borran: titulo y cuenta bancaria del profesor, carnet del apoderado) esta en
supresiones/datos_propios.py. Cuanto tiempo se conserva el historial de pagos y clases queda por definir con
asesoria legal.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notificaciones.models import Notificacion
from supresiones import datos_propios

from .models import Conversacion
from .revision import retenidas

NOMBRE_SUPRIMIDA = 'Cuenta eliminada'


def conversaciones_de(user):
    return Conversacion.objects.filter(Q(cliente=user) | Q(alumno__user=user) | Q(profesor__user=user))


def conversaciones_conservadas(user):
    """Las del usuario que no se pueden borrar: reportadas, salvo las que el lider libero."""
    return conversaciones_de(user).filter(pk__in=retenidas().values('pk'))


def tiene_historial(user):
    """Registros que dependen de la cuenta y se conservan (pagos y clases del alumno; clases con inscripciones,
    paquetes y retiros del profesor; compras y vinculos verificados del apoderado)."""
    return datos_propios.tiene_historial(user)


def _seudonimizar(user):
    user.username = f'eliminada-{user.pk}'
    user.first_name, user.last_name, user.email = NOMBRE_SUPRIMIDA, '', ''
    user.rut, user.telefono, user.direccion = None, '', ''
    user.fecha_nacimiento, user.genero = None, None
    user.is_active, user.suprimida = False, timezone.now()
    user.set_unusable_password()
    user.save()


def suprimir_cuenta(user):
    """True si se borro por completo; False si quedo seudonimizada porque tiene conversaciones reportadas o
    historial de pagos y clases."""
    with transaction.atomic():
        propias = conversaciones_de(user)
        conservadas = conversaciones_conservadas(user)
        borrar = not conservadas.exists() and not tiene_historial(user)
        # Se borre o se seudonimice: la cascada no quita los archivos ni los correos copiados en filas de otros.
        datos_propios.limpiar(user)
        if borrar:
            user.delete()
            return True
        propias.exclude(pk__in=conservadas.values('pk')).delete()
        Notificacion.objects.filter(usuario=user).delete()
        _seudonimizar(user)
        return False
