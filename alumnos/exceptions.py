"""
Excepciones de dominio para el flujo de reservas e inscripciones.
Heredan de ValidationError de Django para garantizar retrocompatibilidad
y permitir control granular de excepciones de dominio en la arquitectura limpia.
"""
from django.core.exceptions import ValidationError


class InscripcionError(ValidationError):
    """Excepción base de dominio para fallos en el proceso de inscripción."""
    def __init__(self, message="Error en el proceso de inscripción.", code=None, params=None):
        super().__init__(message=message, code=code, params=params)


class CupoAgotadoError(InscripcionError):
    """Se dispara cuando una sesión o clase ya no cuenta con cupos libres."""
    def __init__(self, message="No quedan cupos disponibles para esta sesión.", code="cupo_agotado", params=None):
        super().__init__(message=message, code=code, params=params)


class InscripcionDuplicadaError(InscripcionError):
    """Se dispara cuando el alumno ya tiene una inscripción activa o se viola el UniqueConstraint en BD."""
    def __init__(self, message="El alumno ya cuenta con una inscripción activa en esta clase o sesión.", code="duplicado", params=None):
        super().__init__(message=message, code=code, params=params)


class SesionNoDisponibleError(InscripcionError):
    """Se dispara cuando una sesión no está disponible (cancelada, en el pasado, profesor no habilitado)."""
    def __init__(self, message="La sesión solicitada no se encuentra disponible para reservas.", code="no_disponible", params=None):
        super().__init__(message=message, code=code, params=params)
