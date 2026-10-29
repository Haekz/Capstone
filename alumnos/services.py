"""
Servicios del dominio de Alumnos e Inscripciones.
Encapsula la lógica transaccional de reservas y matriculación con control estricto de concurrencia.
"""
import logging
from django.db import transaction, IntegrityError
from django.utils import timezone
from .models import Alumno, Clase, SesionClase, Inscripcion, PaqueteClases
from .utils import es_menor
from .exceptions import (
    InscripcionError,
    CupoAgotadoError,
    InscripcionDuplicadaError,
    SesionNoDisponibleError,
    SinClasesDisponiblesError,
)

logger = logging.getLogger(__name__)

MENSAJE_MENOR = ('Las reservas y compras de estudiantes menores de edad las hace su apoderado '
                 'desde su cuenta.')


def exigir_mayor_de_edad(alumno, vinculo=None):
    """Menores: solo su apoderado reserva, cancela o reprograma por ellos.

    Aqui pasan todas las reservas, asi que el bloqueo cubre tambien cualquier
    vista nueva. ``vinculo`` lo pasan solo las vistas del apoderado; debe
    autorizar a actuar por ese alumno (verificado, propio, apoderado verificado).
    """
    if es_menor(alumno.user) and not (vinculo is not None and vinculo.autoriza(alumno)):
        raise InscripcionError(MENSAJE_MENOR)


def _paquete_con_clases(alumno, profesor, hasta):
    """Paquete vigente del alumno con ese profesor, con clases libres y que vence antes.

    `hasta`: la clase debe tomarse dentro de la vigencia del paquete.
    Bloquea las filas para que dos reservas simultaneas no gasten la misma
    ultima clase. PostgreSQL no admite FOR UPDATE con GROUP BY, por eso las
    usadas se cuentan aparte y no con annotate.
    """
    candidatos = PaqueteClases.objects.select_for_update().filter(
        alumno=alumno, profesor=profesor, estado=PaqueteClases.ESTADO_ACTIVA, fecha_fin__gte=hasta,
    ).order_by('fecha_fin', 'pk')
    for paquete in candidatos:
        if paquete.clases_disponibles:
            return paquete
    raise SinClasesDisponiblesError(
        f'No tienes clases disponibles con {profesor.nombre} para esa fecha. Compra un paquete en Planes.'
    )


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
    def inscribir_alumno_en_sesion(cls, alumno: Alumno, sesion_id: int, vinculo=None) -> Inscripcion:
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
        exigir_mayor_de_edad(alumno, vinculo)
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

            # 5. Cada reserva consume una clase de un paquete pagado
            paquete = _paquete_con_clases(alumno, sesion.clase.profesor, sesion.fecha_hora_inicio)

            # 6. Persistencia protegida contra race-conditions en BD mediante UniqueConstraint
            try:
                inscripcion = Inscripcion.objects.create(
                    alumno=alumno,
                    clase=sesion.clase,
                    sesion=sesion,
                    estado=Inscripcion.ESTADO_CONFIRMADA,
                    paquete=paquete,
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
        exigir_mayor_de_edad(alumno)
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

            paquete = _paquete_con_clases(alumno, clase.profesor, timezone.now())

            try:
                inscripcion = Inscripcion.objects.create(
                    alumno=alumno,
                    clase=clase,
                    sesion=None,
                    estado=Inscripcion.ESTADO_CONFIRMADA,
                    paquete=paquete,
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
    def cancelar_inscripcion(cls, alumno: Alumno, inscripcion_id: int, vinculo=None) -> Inscripcion:
        """
        Cancela una inscripción de forma controlada dentro de una transacción,
        marcando su estado como 'cancelada' para liberar el cupo en consultas concurrentes.
        Si salió de un paquete, la clase vuelve sola: las usadas se cuentan.
        """
        exigir_mayor_de_edad(alumno, vinculo)
        with transaction.atomic():
            try:
                inscripcion = Inscripcion.objects.select_for_update().get(
                    id_inscripcion=inscripcion_id,
                    alumno=alumno
                )
            except Inscripcion.DoesNotExist as exc:
                raise InscripcionError("Inscripción no encontrada o no pertenece al alumno.") from exc

            if not inscripcion.puede_cancelar:
                raise InscripcionError("Esta clase ya comenzó o no está activa: no se puede cancelar.")

            inscripcion.estado = Inscripcion.ESTADO_CANCELADA
            inscripcion.save(update_fields=['estado'])
            return inscripcion

    @classmethod
    def reprogramar_inscripcion(cls, alumno: Alumno, inscripcion_id: int, nueva_sesion_id: int,
                                vinculo=None) -> Inscripcion:
        """
        Mueve una reserva a otra sesion del MISMO profesor sin gastar otra clase del paquete.

        Reglas: la reserva debe estar activa y no haber empezado; la nueva sesion
        debe estar programada, ser futura, tener cupo, no estar ya reservada por el
        alumno y caer dentro de la vigencia del paquete (si la reserva sale de uno).
        """
        exigir_mayor_de_edad(alumno, vinculo)
        with transaction.atomic():
            try:
                # of=('self',): PostgreSQL no bloquea el lado nulo de un outer join (paquete, sesion)
                inscripcion = Inscripcion.objects.select_for_update(of=('self',)).select_related('paquete', 'sesion').get(
                    id_inscripcion=inscripcion_id, alumno=alumno
                )
            except Inscripcion.DoesNotExist as exc:
                raise InscripcionError("Inscripción no encontrada o no pertenece al alumno.") from exc

            if inscripcion.sesion_id is None or not inscripcion.puede_cancelar:
                raise InscripcionError("Esta reserva ya comenzó, no está activa o no tiene una sesión que mover.")

            try:
                nueva = SesionClase.objects.select_for_update().select_related('clase__profesor').get(pk=nueva_sesion_id)
            except SesionClase.DoesNotExist as exc:
                raise SesionNoDisponibleError(f"La sesión #{nueva_sesion_id} no existe.") from exc

            if nueva.pk == inscripcion.sesion_id:
                raise InscripcionError("Elige una sesión distinta a la actual.")
            if nueva.clase.profesor_id != inscripcion.clase.profesor_id:
                raise InscripcionError("Solo puedes reprogramar con el mismo profesor.")
            if nueva.estado != SesionClase.ESTADO_PROGRAMADA or nueva.fecha_hora_inicio <= timezone.now():
                raise SesionNoDisponibleError("La sesión elegida no está disponible para reservas.")
            if not nueva.clase.profesor.puede_hacer_clases:
                raise SesionNoDisponibleError("Esta clase no está disponible: el profesor aún no tiene su título validado.")
            paquete = inscripcion.paquete
            if paquete and nueva.fecha_hora_inicio > paquete.fecha_fin:
                raise SinClasesDisponiblesError("La sesión elegida queda fuera de la vigencia de tu paquete.")

            if nueva.inscripciones.select_for_update().filter(
                alumno=alumno, estado__in=Inscripcion.ESTADOS_ACTIVOS
            ).exists():
                raise InscripcionDuplicadaError("Ya tienes una reserva en esa sesión.")
            ocupados = nueva.inscripciones.select_for_update().filter(estado__in=Inscripcion.ESTADOS_ACTIVOS).count()
            if ocupados >= nueva.cupo_maximo:
                raise CupoAgotadoError("No quedan cupos disponibles para esta sesión.")

            inscripcion.sesion = nueva
            inscripcion.clase = nueva.clase
            try:
                inscripcion.save(update_fields=['sesion', 'clase'])
            except IntegrityError as exc:
                raise InscripcionDuplicadaError("Ya tienes una reserva en esa sesión.") from exc
            return inscripcion
