"""Especializaciones del profesor: subirlas y mostrarlas en su panel (fase 2, 06-nov).

Cada una es un certificado que soporte revisa por separado. Todas las pendientes del profesor van en
un mismo ticket de especializaciones, aparte del ticket del titulo. Maximo 5 en revision a la vez.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from alumnos.models import Asignatura, Especializacion, Profesor
from apoderados import documentos
from soporte.models import Ticket
from soporte.tickets import abrir_ticket

MAXIMO = Especializacion.MAX_EN_REVISION
LARGO_NOMBRE = Especializacion._meta.get_field('nombre').max_length


def _asignaturas(ids):
    """Las del catalogo que eligio. Un id ajeno al catalogo (o manipulado) rechaza todo."""
    ids = set(ids)
    asignaturas = list(Asignatura.objects.filter(pk__in=[i for i in ids if str(i).isdecimal()]))
    if not asignaturas or len(asignaturas) != len(ids):
        raise ValidationError('Elige al menos una asignatura de la lista.')
    return asignaturas


def subir(profesor, nombre, archivo, ids_asignaturas):
    """Guarda la especializacion cifrada, en revision, y la suma al ticket. Lanza ValidationError."""
    nombre = (nombre or '').strip()
    if not nombre:
        raise ValidationError('Indica el nombre de la especialización.')
    if len(nombre) > LARGO_NOMBRE:
        raise ValidationError(f'El nombre puede tener hasta {LARGO_NOMBRE} caracteres.')
    asignaturas = _asignaturas(ids_asignaturas)
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
