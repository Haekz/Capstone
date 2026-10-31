from decimal import Decimal
"""
Servicios del dominio de Alumnos e Inscripciones.
Encapsula la lógica transaccional de reservas y matriculación con control estricto de concurrencia.
"""
import logging
from django.db import transaction, IntegrityError
from django.utils import timezone
from .models import Alumno, Clase, SesionClase, Inscripcion, PaqueteClases
from .utils import es_menor
from django.core.exceptions import ValidationError
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



class PlanesService:
    """Servicio de dominio para cálculo de planes comerciales, liquidaciones y balances (S4-03).
    
    Reglas de negocio oficiales:
    - Precios de referencia para tutor con clase de $15.000:
      * Flexible: 1 clase -> $15.000 (Comisión 15%: $2.250, Tutor 85%: $12.750).
      * Progreso: 4 clases -> $59.000 (Comisión 15%: $8.850, Tutor 85%: $50.150).
      * Intensivo: 8 clases -> $116.000 (Comisión 15%: $17.400, Tutor 85%: $98.600).
    - Comisión LBWUS: 15% IVA incluido sobre precio final.
    - Tutor recibe el 85% restante.
    - Tarifas variables por tutor: se escalan proporcionalmente a los descuentos de referencia.
    - No existen renovaciones automáticas ni suscripciones obligatorias (paquetes prepagados).
    """
    TARIFA_BASE_DEFECTO = 15000
    COMISION_PORCENTAJE = Decimal('0.15')  # 15% IVA incluido

    RATIO_PROGRESO = Decimal('59000') / Decimal('60000')
    RATIO_INTENSIVO = Decimal('116000') / Decimal('120000')

    @classmethod
    def obtener_tarifa_base_profesor(cls, profesor=None):
        if profesor is not None:
            tb = getattr(profesor, 'tarifa_base', None)
            if tb is not None:
                try:
                    return int(Decimal(str(tb)))
                except (ValueError, TypeError):
                    pass
        return cls.TARIFA_BASE_DEFECTO

    @classmethod
    def calcular_precios_plan(cls, tipo_plan, tarifa_base=None):
        """Calcula el precio final, comisión LBWUS y monto bruto para el tutor de un plan específico."""
        if tarifa_base is None:
            tarifa_base = cls.TARIFA_BASE_DEFECTO

        tarifa_dec = Decimal(str(tarifa_base))

        if tipo_plan in ('flexible', 'plan_flexible', '1'):
            clases = 1
            if tarifa_base == cls.TARIFA_BASE_DEFECTO:
                precio_total = 15000
                comision = 2250
                monto_tutor = 12750
            else:
                precio_total = int(round(tarifa_dec))
                comision = int(round(Decimal(str(precio_total)) * cls.COMISION_PORCENTAJE))
                monto_tutor = precio_total - comision

        elif tipo_plan in ('progreso', 'plan_progreso', '2'):
            clases = 4
            if tarifa_base == cls.TARIFA_BASE_DEFECTO:
                precio_total = 59000
                comision = 8850
                monto_tutor = 50150
            else:
                precio_total = int(round(Decimal('4') * tarifa_dec * cls.RATIO_PROGRESO))
                comision = int(round(Decimal(str(precio_total)) * cls.COMISION_PORCENTAJE))
                monto_tutor = precio_total - comision

        elif tipo_plan in ('intensivo', 'plan_intensivo', '3'):
            clases = 8
            if tarifa_base == cls.TARIFA_BASE_DEFECTO:
                precio_total = 116000
                comision = 17400
                monto_tutor = 98600
            else:
                precio_total = int(round(Decimal('8') * tarifa_dec * cls.RATIO_INTENSIVO))
                comision = int(round(Decimal(str(precio_total)) * cls.COMISION_PORCENTAJE))
                monto_tutor = precio_total - comision
        else:
            clases = 1
            precio_total = int(round(tarifa_dec))
            comision = int(round(Decimal(str(precio_total)) * cls.COMISION_PORCENTAJE))
            monto_tutor = precio_total - comision

        return {
            'clases': clases,
            'precio_total': precio_total,
            'comision_lbwus': comision,
            'monto_tutor': monto_tutor,
        }

    @classmethod
    def calcular_planes(cls, profesor=None):
        tarifa_base = cls.obtener_tarifa_base_profesor(profesor)

        planes_info = [
            {
                'id': 'plan_flexible',
                'slug': 'flexible',
                'nombre': 'Plan Flexible',
                'subtitulo': '1 clase individual',
                'clases': 1,
                'descripcion': 'Ideal para resolver dudas puntuales o preparar una evaluación específica.',
                'tipo': 'flexible',
                'popular': False,
            },
            {
                'id': 'plan_progreso',
                'slug': 'progreso',
                'nombre': 'Plan Progreso',
                'subtitulo': 'Paquete de 4 clases',
                'clases': 4,
                'descripcion': 'Acompañamiento mensual para afianzar conocimientos y subir el rendimiento.',
                'tipo': 'progreso',
                'popular': True,
            },
            {
                'id': 'plan_intensivo',
                'slug': 'intensivo',
                'nombre': 'Plan Intensivo',
                'subtitulo': 'Paquete de 8 clases',
                'clases': 8,
                'descripcion': 'Preparación intensiva para exámenes, nivelaciones y metas académicas mayores.',
                'tipo': 'intensivo',
                'popular': False,
            },
        ]

        resultado = []
        for p in planes_info:
            calc = cls.calcular_precios_plan(p['tipo'], tarifa_base=tarifa_base)
            precio_nominal = p['clases'] * tarifa_base
            ahorro = max(0, precio_nominal - calc['precio_total'])
            precio_por_clase = int(round(calc['precio_total'] / p['clases']))

            resultado.append({
                'id': p['id'],
                'slug': p['slug'],
                'nombre': p['nombre'],
                'subtitulo': p['subtitulo'],
                'clases': p['clases'],
                'descripcion': p['descripcion'],
                'precio_total': calc['precio_total'],
                'precio_formateado': f"${calc['precio_total']:,}".replace(',', '.'),
                'precio_por_clase': precio_por_clase,
                'precio_por_clase_formateado': f"${precio_por_clase:,}".replace(',', '.'),
                'comision_lbwus': calc['comision_lbwus'],
                'comision_lbwus_formateado': f"${calc['comision_lbwus']:,}".replace(',', '.'),
                'monto_tutor': calc['monto_tutor'],
                'monto_tutor_formateado': f"${calc['monto_tutor']:,}".replace(',', '.'),
                'ahorro': ahorro,
                'ahorro_formateado': f"${ahorro:,}".replace(',', '.'),
                'es_popular': p['popular'],
                'sin_renovacion': True,
            })
        return resultado

    @classmethod
    def crear_plan_desde_pago(cls, alumno, tipo_plan_str, pago, profesor=None):
        from .models import PlanAlumno
        tipo_normalizado = str(tipo_plan_str).lower().replace('plan_', '')
        if tipo_normalizado not in ('flexible', 'progreso', 'intensivo'):
            tipo_normalizado = 'flexible'

        tarifa_base = cls.obtener_tarifa_base_profesor(profesor)
        calc = cls.calcular_precios_plan(tipo_normalizado, tarifa_base=tarifa_base)

        with transaction.atomic():
            plan = PlanAlumno.objects.create(
                alumno=alumno,
                profesor=profesor,
                tipo_plan=tipo_normalizado,
                total_clases=calc['clases'],
                clases_disponibles=calc['clases'],
                clases_consumidas=0,
                monto_total=calc['precio_total'],
                comision_lbwus=calc['comision_lbwus'],
                monto_tutor=calc['monto_tutor'],
                pago=pago,
                estado=PlanAlumno.ESTADO_ACTIVO
            )
            # S4-09: Registro contable inmutable de la operación de compra
            LiquidacionService.registrar_compra(
                pago=pago,
                alumno=alumno,
                profesor=profesor,
                plan_alumno=plan
            )
            return plan

    @classmethod
    def consumir_clase_de_plan(cls, alumno, profesor=None, sesion=None):
        from .models import PlanAlumno
        with transaction.atomic():
            query = PlanAlumno.objects.select_for_update().filter(
                alumno=alumno,
                estado=PlanAlumno.ESTADO_ACTIVO,
                clases_disponibles__gt=0
            )
            if profesor is not None:
                plan = query.filter(profesor=profesor).order_by('created_at').first()
                if not plan:
                    plan = query.filter(profesor__isnull=True).order_by('created_at').first()
            else:
                plan = query.order_by('created_at').first()

            if not plan:
                from .exceptions import PlanSinSaldoError
                raise PlanSinSaldoError("No tienes saldo de clases disponible en tus planes activos.")

            plan.consumir_clase()
            # S4-09: Registro y devengo contable de la clase consumida
            LiquidacionService.registrar_consumo_clase(
                plan_alumno=plan,
                profesor=profesor or plan.profesor
            )
            return plan



class LiquidacionService:
    """Servicio financiero para registro contable, comisiones LBWUS (15% IVA inc.) y liquidaciones (S4-09).

    Reglas de negocio:
    - Comisión LBWUS: 15% IVA incluido sobre precio final.
    - Tutor recibe el 85% restante.
    - Precios de referencia obligatorios:
      * $15.000 -> Comisión bruta $2.250 | Tutor $12.750
      * $59.000 -> Comisión bruta $8.850 | Tutor $50.150
      * $116.000 -> Comisión bruta $17.400 | Tutor $98.600
    - Desglose de IVA: 19% dentro de la comisión de la plataforma.
    """
    TASA_COMISION = Decimal('0.15')
    TASA_IVA = Decimal('0.19')

    VALORES_CANONICOS = {
        15000: {'comision': 2250, 'tutor': 12750},
        59000: {'comision': 8850, 'tutor': 50150},
        116000: {'comision': 17400, 'tutor': 98600},
    }

    @classmethod
    def calcular_desglose(cls, monto_bruto):
        """Calcula el desglose económico de una operación según la regla del 15% IVA incluido."""
        monto_int = int(monto_bruto)
        if monto_int in cls.VALORES_CANONICOS:
            comision = cls.VALORES_CANONICOS[monto_int]['comision']
            monto_tutor = cls.VALORES_CANONICOS[monto_int]['tutor']
        else:
            comision = int(round(Decimal(str(monto_int)) * cls.TASA_COMISION))
            monto_tutor = monto_int - comision

        # Desglose del IVA (19%) sobre la comisión retenida por LBWUS
        neto_comision = int(round(Decimal(str(comision)) / (Decimal('1') + cls.TASA_IVA)))
        iva_comision = comision - neto_comision

        return {
            'monto_bruto': monto_int,
            'comision_lbwus': comision,
            'neto_comision': neto_comision,
            'iva_comision': iva_comision,
            'monto_tutor': monto_tutor,
        }

    @classmethod
    def registrar_compra(cls, pago, alumno, profesor=None, plan_alumno=None, inscripcion=None, tipo_operacion=None):
        from .models import DesgloseOperacion
        monto_total = pago.monto if pago else (plan_alumno.monto_total if plan_alumno else 15000)
        calc = cls.calcular_desglose(monto_total)

        if not tipo_operacion:
            tipo_operacion = DesgloseOperacion.TIPO_COMPRA_PLAN if plan_alumno else DesgloseOperacion.TIPO_CLASE_INDIVIDUAL

        if plan_alumno and plan_alumno.total_clases > 1:
            estado_inicial = DesgloseOperacion.ESTADO_PENDIENTE
        else:
            estado_inicial = DesgloseOperacion.ESTADO_DISPONIBLE

        with transaction.atomic():
            desglose = DesgloseOperacion.objects.create(
                pago=pago,
                alumno=alumno,
                profesor=profesor,
                plan_alumno=plan_alumno,
                inscripcion=inscripcion,
                tipo_operacion=tipo_operacion,
                estado=estado_inicial,
                monto_bruto=calc['monto_bruto'],
                comision_lbwus=calc['comision_lbwus'],
                iva_comision=calc['iva_comision'],
                neto_comision=calc['neto_comision'],
                monto_tutor=calc['monto_tutor'],
                fecha_liberacion=timezone.now() if estado_inicial == DesgloseOperacion.ESTADO_DISPONIBLE else None
            )
            return desglose

    @classmethod
    def registrar_consumo_clase(cls, plan_alumno, inscripcion=None, profesor=None):
        """Asocia el devengo de una clase ejecutada a un plan adquirido, liberando la cuota del tutor."""
        from .models import DesgloseOperacion
        if not plan_alumno or plan_alumno.total_clases <= 0:
            return None

        cuota_bruta = int(round(plan_alumno.monto_total / plan_alumno.total_clases))
        cuota_comision = int(round(plan_alumno.comision_lbwus / plan_alumno.total_clases))
        cuota_tutor = int(round(plan_alumno.monto_tutor / plan_alumno.total_clases))

        neto_comision = int(round(Decimal(str(cuota_comision)) / (Decimal('1') + cls.TASA_IVA)))
        iva_comision = cuota_comision - neto_comision

        tutor_efectivo = profesor or plan_alumno.profesor
        if not tutor_efectivo and inscripcion and hasattr(inscripcion, 'clase') and inscripcion.clase:
            tutor_efectivo = inscripcion.clase.profesor

        with transaction.atomic():
            desglose = DesgloseOperacion.objects.create(
                pago=plan_alumno.pago,
                alumno=plan_alumno.alumno,
                profesor=tutor_efectivo,
                plan_alumno=plan_alumno,
                inscripcion=inscripcion,
                tipo_operacion=DesgloseOperacion.TIPO_CONSUMO_CLASE,
                estado=DesgloseOperacion.ESTADO_DISPONIBLE,
                monto_bruto=cuota_bruta,
                comision_lbwus=cuota_comision,
                iva_comision=iva_comision,
                neto_comision=neto_comision,
                monto_tutor=cuota_tutor,
                fecha_liberacion=timezone.now(),
                notas_auditoria=f"Clase consumida de {plan_alumno.get_tipo_plan_display()}"
            )
            return desglose

    @classmethod
    def procesar_reembolso(cls, desglose_id_o_obj, motivo="Reembolso solicitado por cancelación"):
        """Ejecuta la anulación/reverso contable y protege los fondos de cobros indebidos."""
        from .models import DesgloseOperacion
        with transaction.atomic():
            if isinstance(desglose_id_o_obj, DesgloseOperacion):
                desglose = desglose_id_o_obj
            else:
                desglose = DesgloseOperacion.objects.select_for_update().get(pk=desglose_id_o_obj)

            if desglose.estado == DesgloseOperacion.ESTADO_REEMBOLSADO:
                return desglose

            desglose.estado = DesgloseOperacion.ESTADO_REEMBOLSADO
            desglose.notas_auditoria = (desglose.notas_auditoria + f" | Reembolso: {motivo}").strip(" | ")
            desglose.save(update_fields=['estado', 'notas_auditoria'])

            if desglose.plan_alumno:
                try:
                    desglose.plan_alumno.reembolsar_clase()
                except ValidationError:
                    pass

            if desglose.inscripcion:
                from .models import Inscripcion
                desglose.inscripcion.estado = Inscripcion.ESTADO_CANCELADA
                desglose.inscripcion.save(update_fields=['estado'])

            return desglose
