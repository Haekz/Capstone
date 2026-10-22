"""
Servicios del dominio de Alumnos e Inscripciones.
Encapsula la lógica transaccional de reservas y matriculación con control estricto de concurrencia.
"""
import logging
from django.db import transaction, IntegrityError
from django.utils import timezone
from .models import Alumno, Clase, SesionClase, Inscripcion
from .exceptions import (
    InscripcionError,
    CupoAgotadoError,
    InscripcionDuplicadaError,
    SesionNoDisponibleError,
)

logger = logging.getLogger(__name__)


class InscripcionService:
    """
    Servicio de Dominio para la gestión transaccional de inscripciones y reservas.
    Implementa:
    - Bloqueo a nivel de fila (select_for_update) sobre la entidad SesionClase o Clase.
    - Re-verificación atómica de disponibilidad y conteo de cupos restantes.
    - Captura y traducción de excepciones por violación de UniqueConstraint a nivel de PostgreSQL.
    - Operaciones completamente rollback-safe mediante transaction.atomic().
    """

    @classmethod
    def inscribir_alumno_en_sesion(cls, alumno: Alumno, sesion_id: int) -> Inscripcion:
        """
        Inscribe atómicamente a un alumno en una SesionClase puntual.

        Parámetros:
            alumno (Alumno): Instancia del alumno solicitante.
            sesion_id (int): ID de la sesión a reservar.

        Retorna:
            Inscripcion: Registro de inscripción creado con estado 'confirmada'.

        Lanza:
            SesionNoDisponibleError: Si la sesión no existe, ya pasó, fue cancelada o el profesor no está habilitado.
            InscripcionDuplicadaError: Si el alumno ya está inscrito activamente en la sesión (o colisión de BD).
            CupoAgotadoError: Si el número de inscripciones activas alcanza o supera el cupo máximo.
        """
        with transaction.atomic():
            # 1. Bloqueo pesimista a nivel de fila (select_for_update)
            try:
                sesion = SesionClase.objects.select_for_update().get(pk=sesion_id)
            except SesionClase.DoesNotExist as exc:
                raise SesionNoDisponibleError(f"La sesión #{sesion_id} no existe.") from exc

            # 2. Validaciones de disponibilidad y estado
            if sesion.estado != SesionClase.ESTADO_PROGRAMADA:
                raise SesionNoDisponibleError("La sesión no se encuentra disponible para reservas.")

            if sesion.fecha_hora_inicio <= timezone.now():
                raise SesionNoDisponibleError("No se pueden reservar sesiones cuya fecha de inicio ya transcurrió.")

            if not sesion.clase.profesor.puede_hacer_clases:
                raise SesionNoDisponibleError("Esta clase no está disponible: el profesor aún no tiene su título validado.")

            # 3. Validar si el alumno ya está inscrito activamente (dentro de la transacción bloqueada)
            ya_inscrito = sesion.inscripciones.select_for_update().filter(
                alumno=alumno,
                estado__in=[Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_PENDIENTE]
            ).exists()

            if ya_inscrito:
                raise InscripcionDuplicadaError("El alumno ya está inscrito en esta sesión.")

            # 4. Re-verificación de cupos restantes bloqueando el conteo de inscripciones
            total_ocupados = sesion.inscripciones.select_for_update().filter(
                estado__in=[Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_PENDIENTE]
            ).count()

            if total_ocupados >= sesion.cupo_maximo:
                raise CupoAgotadoError("No quedan cupos disponibles para esta sesión.")

            # 5. Persistencia protegida contra race-conditions en BD mediante UniqueConstraint
            try:
                inscripcion = Inscripcion.objects.create(
                    alumno=alumno,
                    clase=sesion.clase,
                    sesion=sesion,
                    estado=Inscripcion.ESTADO_CONFIRMADA
                )
            except IntegrityError as exc:
                logger.warning(
                    "IntegrityError capturado en BD para Alumno ID %s en Sesion ID %s: %s",
                    alumno.pk, sesion.pk, exc
                )
                raise InscripcionDuplicadaError(
                    "El alumno ya está inscrito en esta sesión (forzado por base de datos)."
                ) from exc

            return inscripcion

    @classmethod
    def inscribir_alumno_en_clase(cls, alumno: Alumno, clase_id: int) -> Inscripcion:
        """
        Inscribe atómicamente a un alumno en una Clase general (sin sesión puntual).
        Mantiene el flujo preexistente de inscripción general pero protegido con select_for_update
        y control de unicidad a nivel de PostgreSQL.
        """
        with transaction.atomic():
            try:
                clase = Clase.objects.select_for_update().get(pk=clase_id)
            except Clase.DoesNotExist as exc:
                raise SesionNoDisponibleError(f"La clase #{clase_id} no existe.") from exc

            if not clase.profesor.puede_hacer_clases:
                raise SesionNoDisponibleError(
                    "Esta clase no está disponible: el profesor aún no tiene su título validado."
                )

            ya_inscrito = Inscripcion.objects.select_for_update().filter(
                alumno=alumno,
                clase=clase,
                sesion__isnull=True,
                estado__in=[Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_PENDIENTE]
            ).exists()

            if ya_inscrito:
                raise InscripcionDuplicadaError(
                    f'Ya estás inscrito en la clase "{clase.asignatura.nombre}".'
                )

            try:
                inscripcion = Inscripcion.objects.create(
                    alumno=alumno,
                    clase=clase,
                    sesion=None,
                    estado=Inscripcion.ESTADO_CONFIRMADA
                )
            except IntegrityError as exc:
                logger.warning(
                    "IntegrityError capturado en BD para Alumno ID %s en Clase ID %s: %s",
                    alumno.pk, clase.pk, exc
                )
                raise InscripcionDuplicadaError(
                    f'Ya estás inscrito en la clase "{clase.asignatura.nombre}" (forzado por base de datos).'
                ) from exc

            return inscripcion

    @classmethod
    def cancelar_inscripcion(cls, alumno: Alumno, inscripcion_id: int) -> Inscripcion:
        """
        Cancela una inscripción de forma controlada dentro de una transacción,
        marcando su estado como 'cancelada' para liberar el cupo en consultas concurrentes.
        """
        with transaction.atomic():
            try:
                inscripcion = Inscripcion.objects.select_for_update().get(
                    id_inscripcion=inscripcion_id,
                    alumno=alumno
                )
            except Inscripcion.DoesNotExist as exc:
                raise InscripcionError("Inscripción no encontrada o no pertenece al alumno.") from exc

            inscripcion.estado = Inscripcion.ESTADO_CANCELADA
            inscripcion.save(update_fields=['estado'])
            return inscripcion
