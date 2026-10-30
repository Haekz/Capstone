"""
Suite de Pruebas Automatizadas para S4-09:
Validar saldos, comisiones y liquidaciones bajo comisión LBWUS del 15% IVA incluido.

Criterios a validar:
1. Verificación matemática exacta de comisiones brutas LBWUS (15% IVA incluido):
   - CLP 15.000 -> CLP 2.250 de comisión bruta (Tutor: CLP 12.750).
   - CLP 59.000 -> CLP 8.850 de comisión bruta (Tutor: CLP 50.150).
   - CLP 116.000 -> CLP 17.400 de comisión bruta (Tutor: CLP 98.600).
2. Desglose impositivo de IVA (19%) en comisiones y consistencia de sumas:
   - neto_comision + iva_comision == comision_lbwus
   - comision_lbwus + monto_tutor == monto_bruto
3. Asociación de importes a compra (Pago) y paquete (PlanAlumno).
4. Asociación de importes devengados a clases ejecutadas (Inscripcion).
5. Identificación de importes pendientes (fondos retenidos en custodia por clases no dictadas).
6. Circuito de reembolsos y anulación de derechos de cobro del tutor.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from alumnos.models import (
    Alumno, Profesor, Especialidad, Genero,
    Pago, PlanAlumno, Clase, Asignatura, Inscripcion, DesgloseOperacion
)
from alumnos.services import PlanesService, LiquidacionService
from user_profesor.views import calcular_saldos

User = get_user_model()


class LiquidacionesComisionesS409Tests(TestCase):

    def setUp(self):
        self.genero = Genero.objects.create(descripcion='Otro')
        self.especialidad = Especialidad.objects.create(nombre='Física')
        self.asignatura = Asignatura.objects.create(nombre='Mecánica Clásica')

        # Alumno
        self.u_alumno = User.objects.create_user(
            username='alumno_s409',
            email='alumno_s409@lbwus.cl',
            password='Password123!',
            rol='alumno'
        )
        self.alumno = Alumno.objects.create(user=self.u_alumno)

        # Profesor
        self.u_profesor = User.objects.create_user(
            username='profesor_s409',
            email='profesor_s409@lbwus.cl',
            password='Password123!',
            first_name='Richard',
            last_name='Feynman',
            rol='profesor'
        )
        self.profesor = Profesor.objects.create(
            user=self.u_profesor,
            especialidad=self.especialidad,
            titulo_estado=Profesor.TITULO_APROBADO,
            tarifa_base=Decimal('15000.00')
        )

        self.clase = Clase.objects.create(
            asignatura=self.asignatura,
            profesor=self.profesor,
            modalidad='online',
            horario='09:00:00'
        )

    # -------------------------------------------------------------------------
    # 1. VERIFICACIÓN DE COMISIONES BRUTAS DE REFERENCIA ($2.250, $8.850, $17.400)
    # -------------------------------------------------------------------------

    def test_01_comisiones_brutas_referenciales_exactas(self):
        """Valida exactamente CLP 2.250, 8.850 y 17.400 de comisión bruta (S4-09)."""
        # Flexible: $15.000
        d_flex = LiquidacionService.calcular_desglose(15000)
        self.assertEqual(d_flex['monto_bruto'], 15000)
        self.assertEqual(d_flex['comision_lbwus'], 2250)
        self.assertEqual(d_flex['monto_tutor'], 12750)
        self.assertEqual(d_flex['comision_lbwus'] + d_flex['monto_tutor'], 15000)

        # Progreso: $59.000
        d_prog = LiquidacionService.calcular_desglose(59000)
        self.assertEqual(d_prog['monto_bruto'], 59000)
        self.assertEqual(d_prog['comision_lbwus'], 8850)
        self.assertEqual(d_prog['monto_tutor'], 50150)
        self.assertEqual(d_prog['comision_lbwus'] + d_prog['monto_tutor'], 59000)

        # Intensivo: $116.000
        d_inte = LiquidacionService.calcular_desglose(116000)
        self.assertEqual(d_inte['monto_bruto'], 116000)
        self.assertEqual(d_inte['comision_lbwus'], 17400)
        self.assertEqual(d_inte['monto_tutor'], 98600)
        self.assertEqual(d_inte['comision_lbwus'] + d_inte['monto_tutor'], 116000)

    # -------------------------------------------------------------------------
    # 2. DESGLOSE DE IVA DÉBITO FISCAL (19%) EN COMISIONES
    # -------------------------------------------------------------------------

    def test_02_desglose_iva_fiscal_en_comisiones(self):
        """Valida que la comisión del 15% IVA incluido descomponga neto e IVA correctamente."""
        for monto in [15000, 59000, 116000]:
            d = LiquidacionService.calcular_desglose(monto)
            comision = d['comision_lbwus']
            neto = d['neto_comision']
            iva = d['iva_comision']

            # La suma de neto + IVA debe igualar la comisión exacta
            self.assertEqual(neto + iva, comision, f"Fallo de suma impositiva en monto {monto}")
            # Verificación del ratio del 19%: iva ~= neto * 0.19
            self.assertAlmostEqual(float(iva) / float(neto), 0.19, delta=0.01)

    # -------------------------------------------------------------------------
    # 3. ASOCIACIÓN DE IMPORTES A COMPRA (PAGO) Y PLAN (PLAN_ALUMNO)
    # -------------------------------------------------------------------------

    def test_03_asociacion_desglose_a_compra_y_plan(self):
        """Verifica que la compra de un plan cree su registro contable con claves foráneas íntegras."""
        pago = Pago.objects.create(
            buy_order='LB-S409-COMPRA-01',
            monto=59000,
            estado=Pago.ESTADO_PAGADA
        )

        plan = PlanesService.crear_plan_desde_pago(
            alumno=self.alumno,
            tipo_plan_str='progreso',
            pago=pago,
            profesor=self.profesor
        )

        # Buscar el desglose generado automáticamente
        desglose = DesgloseOperacion.objects.filter(pago=pago, plan_alumno=plan).first()
        self.assertIsNotNone(desglose)
        self.assertEqual(desglose.tipo_operacion, DesgloseOperacion.TIPO_COMPRA_PLAN)
        self.assertEqual(desglose.alumno, self.alumno)
        self.assertEqual(desglose.profesor, self.profesor)
        self.assertEqual(desglose.monto_bruto, 59000)
        self.assertEqual(desglose.comision_lbwus, 8850)
        self.assertEqual(desglose.monto_tutor, 50150)
        # Fondos de paquetes de clases inician en custodia/pendiente para salvaguardar reembolsos
        self.assertEqual(desglose.estado, DesgloseOperacion.ESTADO_PENDIENTE)

    # -------------------------------------------------------------------------
    # 4. ASOCIACIÓN DE IMPORTES A CLASES EJECUTADAS
    # -------------------------------------------------------------------------

    def test_04_asociacion_desglose_a_clase_consumida(self):
        """Al dictar una clase del plan, se devenga y asocia un desglose en estado 'disponible'."""
        pago = Pago.objects.create(
            buy_order='LB-S409-CONSUMO-01',
            monto=59000,
            estado=Pago.ESTADO_PAGADA
        )
        plan = PlanesService.crear_plan_desde_pago(
            alumno=self.alumno,
            tipo_plan_str='progreso',
            pago=pago,
            profesor=self.profesor
        )

        # Consumir una clase
        plan_actualizado = PlanesService.consumir_clase_de_plan(
            alumno=self.alumno,
            profesor=self.profesor
        )

        # Verificar desglose devengado por la clase
        desgloses_consumo = DesgloseOperacion.objects.filter(
            plan_alumno=plan,
            tipo_operacion=DesgloseOperacion.TIPO_CONSUMO_CLASE
        )
        self.assertEqual(desgloses_consumo.count(), 1)
        des_clase = desgloses_consumo.first()
        self.assertEqual(des_clase.estado, DesgloseOperacion.ESTADO_DISPONIBLE)
        self.assertEqual(des_clase.profesor, self.profesor)
        # Cuota de 1 clase en plan progreso ($50.150 / 4 = $12.538 aprox)
        self.assertTrue(des_clase.monto_tutor > 12000)

    # -------------------------------------------------------------------------
    # 5. IDENTIFICACIÓN DE IMPORTES PENDIENTES
    # -------------------------------------------------------------------------

    def test_05_identificacion_importes_pendientes(self):
        """Verifica la distinción entre clases en custodia (pendiente) y saldo liberado (disponible)."""
        pago = Pago.objects.create(
            buy_order='LB-S409-PENDIENTES',
            monto=59000,
            estado=Pago.ESTADO_PAGADA
        )
        plan = PlanesService.crear_plan_desde_pago(
            alumno=self.alumno,
            tipo_plan_str='progreso',
            pago=pago,
            profesor=self.profesor
        )

        # 0 clases dictadas: $0 disponible, los $50.150 del tutor permanecen en pendiente
        saldos_cero = calcular_saldos(self.profesor)
        self.assertEqual(saldos_cero['disponible'], 0)
        self.assertEqual(saldos_cero['pendiente'], 59000)

        # Dictar 2 clases de 4
        PlanesService.consumir_clase_de_plan(alumno=self.alumno, profesor=self.profesor)
        PlanesService.consumir_clase_de_plan(alumno=self.alumno, profesor=self.profesor)

        saldos_dos = calcular_saldos(self.profesor)
        esperado_disponible = int(round((50150 / 4) * 2))  # $25.075
        self.assertEqual(saldos_dos['disponible'], esperado_disponible)
        self.assertEqual(saldos_dos['pendiente'], 59000 - esperado_disponible)

    # -------------------------------------------------------------------------
    # 6. CIRCUITO DE REEMBOLSOS Y ANULACIONES
    # -------------------------------------------------------------------------

    def test_06_circuito_reembolso_y_anulacion_de_fondos(self):
        """Un reembolso cambia el estado a 'reembolsado', restituye clases y previene retiros indebidos."""
        pago = Pago.objects.create(
            buy_order='LB-S409-REEMBOLSO-01',
            monto=15000,
            estado=Pago.ESTADO_PAGADA
        )
        inscripcion = Inscripcion.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            pago=pago,
            estado=Inscripcion.ESTADO_CONFIRMADA
        )
        desglose = LiquidacionService.registrar_compra(
            pago=pago,
            alumno=self.alumno,
            profesor=self.profesor,
            inscripcion=inscripcion,
            tipo_operacion=DesgloseOperacion.TIPO_CLASE_INDIVIDUAL
        )

        self.assertEqual(desglose.estado, DesgloseOperacion.ESTADO_DISPONIBLE)

        # Procesar reembolso por cancelación oportuna
        desglose_reembolsado = LiquidacionService.procesar_reembolso(
            desglose,
            motivo="Cancelación con más de 24h de anticipación"
        )

        self.assertEqual(desglose_reembolsado.estado, DesgloseOperacion.ESTADO_REEMBOLSADO)
        self.assertIn("Cancelación con más de 24h", desglose_reembolsado.notas_auditoria)

        # La inscripción asociada debe quedar cancelada
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.estado, Inscripcion.ESTADO_CANCELADA)

        # El profesor no debe tener fondos disponibles por esta inscripción cancelada
        saldos = calcular_saldos(self.profesor)
        self.assertEqual(saldos['disponible'], 0)
