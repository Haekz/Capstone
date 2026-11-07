"""Modelos de la app alumnos, separados por tema. Se reexportan aqui para que Django los registre
y para que ``from alumnos.models import X`` siga funcionando en todo el proyecto."""

from .usuarios import Alumno, CustomUser, Especialidad, Genero, Profesor, ProfesorQuerySet, Tutor
from .clases import (
    Asignatura, Clase, ClaseQuerySet, Inscripcion, InscripcionQuerySet, SesionClase, SesionClaseManager,
    SesionClaseQuerySet,
)
from .pagos import PaqueteClases, PaqueteClasesQuerySet, Suscripcion, SuscripcionQuerySet
from .especializaciones import Especializacion
from .reportes import Reporte
from .retiros import TIPOS_CUENTA, Banco, CuentaBancaria, SolicitudRetiro

__all__ = [
    'Alumno', 'CustomUser', 'Especialidad', 'Genero', 'Profesor', 'ProfesorQuerySet', 'Tutor',
    'Asignatura', 'Clase', 'ClaseQuerySet', 'Inscripcion', 'InscripcionQuerySet', 'SesionClase',
    'SesionClaseManager', 'SesionClaseQuerySet',
    'PaqueteClases', 'PaqueteClasesQuerySet', 'Suscripcion', 'SuscripcionQuerySet',
    'Especializacion',
    'Reporte',
    'TIPOS_CUENTA', 'Banco', 'CuentaBancaria', 'SolicitudRetiro',
]
