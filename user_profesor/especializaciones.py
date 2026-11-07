"""Especializaciones del profesor: subirlas, mostrarlas en su panel y decidirlas (fase 2, 06-nov).

Cada una es un certificado que soporte revisa por separado. Todas las pendientes del profesor van en
un mismo ticket de especializaciones, aparte del ticket del titulo. Maximo 5 en revision a la vez.
Al decidir, el documento se borra (como el titulo) y, si no queda ninguna pendiente, se cierra el ticket.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from alumnos.models import Asignatura, Especializacion, Profesor
from apoderados import documentos
from soporte.models import Ticket
from soporte.tickets import abrir_ticket, cerrar_tickets

from .asignaturas import asignar, del_catalogo

MAXIMO = Especializacion.MAX_EN_REVISION
LARGO_NOMBRE = Especializacion._meta.get_field('nombre').max_length


def subir(profesor, nombre, archivo, ids_asignaturas):
    """Guarda la especializacion cifrada, en revision, y la suma al ticket. Lanza ValidationError."""
    nombre = (nombre or '').strip()
    if not nombre:
        raise ValidationError('Indica el nombre de la especialización.')
    if len(nombre) > LARGO_NOMBRE:
        raise ValidationError(f'El nombre puede tener hasta {LARGO_NOMBRE} caracteres.')
    asignaturas = del_catalogo(ids_asignaturas, obligatoria=True)
    if archivo is None:
        raise ValidationError('Selecciona el archivo del certificado.')
    contenido, formato = documentos.preparar(archivo)
    with transaction.atomic():
        Profesor.objects.select_for_update().filter(pk=profesor.pk).first()  # dos envios a la vez: uno espera
        if profesor.especializaciones.filter(estado=Especializacion.EN_REVISION).count() >= MAXIMO:
            raise ValidationError(f'Ya tienes {MAXIMO} especializaciones en revisión. '
                                  'Cuando soporte las revise podrás subir más.')
        especializacion = Especializacion.objects.create(profesor=profesor, nombre=nombre,
                                                         contenido=contenido, formato=formato)
        especializacion.propuestas.set(asignaturas)
        abrir_ticket(Ticket.ESPECIALIZACIONES, profesor=profesor)
    return especializacion


def resolver(especializacion, aprobar, observacion='', ids_asignaturas=()):
    """Decision de soporte sobre una especializacion en revision. El documento se borra (como el titulo).

    Al aprobar, soporte elige las asignaturas que podra dictar (al menos una; las propuestas van premarcadas,
    pero puede elegir cualquiera del catalogo) y se crean sus clases. Devuelve las clases nuevas.
    """
    observacion = (observacion or '').strip()
    if not aprobar and not observacion:
        raise ValidationError('Indica el motivo del rechazo.')
    elegidas = del_catalogo(ids_asignaturas, obligatoria=True) if aprobar else []
    with transaction.atomic():
        Profesor.objects.select_for_update().filter(pk=especializacion.profesor_id).first()  # ver el cierre abajo
        decididas = Especializacion.objects.filter(pk=especializacion.pk, estado=Especializacion.EN_REVISION).update(
            estado=Especializacion.APROBADA if aprobar else Especializacion.RECHAZADA,
            observacion='' if aprobar else observacion[:200], revisada=timezone.now(), contenido=None, formato='')
        if not decididas:  # ya la decidio otro agente
            raise ValidationError('Esa especialización no está pendiente de revisión.')
        nuevas = asignar(especializacion.profesor, elegidas)  # con el profesor bloqueado: no se duplican
        pendientes = Especializacion.objects.filter(profesor_id=especializacion.profesor_id,
                                                    estado=Especializacion.EN_REVISION)
        if not pendientes.exists():  # con el profesor bloqueado: dos decisiones a la vez no dejan el ticket abierto
            cerrar_tickets(Ticket.objects.filter(profesor_id=especializacion.profesor_id,
                                                 categoria=Ticket.ESPECIALIZACIONES))
    especializacion.refresh_from_db()
    return nuevas


def contexto_panel(profesor):
    """Lo que necesita la seccion "Mis especializaciones" del panel. Nunca el documento."""
    especializaciones = list(profesor.especializaciones.defer('contenido').prefetch_related('propuestas'))
    en_revision = sum(e.estado == Especializacion.EN_REVISION for e in especializaciones)
    return {
        'especializaciones': especializaciones,
        'asignaturas_catalogo': Asignatura.objects.order_by('nombre'),
        'puede_subir_especializacion': en_revision < MAXIMO,
        'max_especializaciones': MAXIMO,
        'largo_nombre_especializacion': LARGO_NOMBRE,
    }
