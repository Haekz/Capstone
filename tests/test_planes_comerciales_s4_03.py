"""
Suite de Pruebas Automatizadas para S4-03:
Configurar planes Flexible, Progreso e Intensivo y reglas comerciales.

Criterios a validar:
1. Exactitud matemática en precios de referencia ($15.000 base):
   - Flexible: $15.000 final, $2.250 LBWUS (15%), $12.750 tutor (85%).
   - Progreso: $59.000 final, $8.850 LBWUS (15%), $50.150 tutor (85%).
   - Intensivo: $116.000 final, $17.400 LBWUS (15%), $98.600 tutor (85%).
2. Integridad de suma: precio_total == comision_lbwus + monto_tutor.
3. Tarifas variables por tutor con descuentos proporcionales.
4. Ciclo de vida y saldo decreciente de PlanAlumno (creación, consumo atómico, estado agotado).
5. Protección contra cobros anticipados en liquidación docente (user_profesor.calcular_saldos).
6. Prevención de renovaciones automáticas y suscripciones recurrentes forzadas.
7. Endpoint público de planes responde estructura oficial en HTML y JSON.
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from alumnos.models import (
    Alumno, Profesor, Especialidad, Genero,
    Pago, PlanAlumno, Clase, Asignatura, Inscripcion
)
from alumnos.services import PlanesService
from alumnos.exceptions import PlanSinSaldoError
from user_profesor.views import calcular_saldos, VALOR_INSCRIPCION, PAGO_PROFESOR, COMISION_LBWUS

User = get_user_model()


class PlanesComercialesS403Tests(TestCase):

    def setUp(self):
        self.client = Client()

        self.genero = Genero.objects.create(descripcion='Otro')
        self.especialidad = Especialidad.objects.create(nombre='Matemáticas')
        self.asignatura = Asignatura.objects.create(nombre='Álgebra Lineal')

        # Usuario Alumno
        self.u_alumno = User.objects.create_user(
            username='alumno_s4',
            email='alumno_s4@lbwus.cl',
            password='Password123!',
            rol='alumno'
        )
        self.alumno = Alumno.objects.create(user=self.u_alumno)

        # Usuario Profesor con tarifa de referencia ($15.000)
        self.u_profesor = User.objects.create_user(
            username='profe_ref',
            email='profe_ref@lbwus.cl',
            password='Password123!',
            first_name='Alan',
            last_name='Turing',
            rol='profesor'
        )
        self.profesor_ref = Profesor.objects.create(
            user=self.u_profesor,
            especialidad=self.especialidad,
            titulo_estado=Profesor.TITULO_APROBADO,
            tarifa_base=Decimal('15000.00')
        )

        # Usuario Profesor con tarifa variable ($20.000)
        self.u_profesor_var = User.objects.create_user(
            username='profe_var',
            email='profe_var@lbwus.cl',
            password='Password123!',
            first_name='Ada',
            last_name='Lovelace',
            rol='profesor'
        )
        self.profesor_var = Profesor.objects.create(
            user=self.u_profesor_var,
            especialidad=self.especialidad,
            titulo_estado=Profesor.TITULO_APROBADO,
            tarifa_base=Decimal('20000.00')
        )

        self.clase = Clase.objects.create(
            asignatura=self.asignatura,
            profesor=self.profesor_ref,
            modalidad='online',
            horario='10:00:00'
        )

    # -------------------------------------------------------------------------
    # 1. PRUEBAS MATEMÁTICAS EN TARIFAS DE REFERENCIA ($15.000)
    # -------------------------------------------------------------------------

    def test_01_precios_oficiales_y_comision_15_tarifa_referencia(self):
        """Valida que los importes de referencia coincidan exactamente con la especificación S4-03."""
        # Flexible (1 clase @ $15.000)
        flex = PlanesService.calcular_precios_plan('flexible', tarifa_base=15000)
        self.assertEqual(flex['clases'], 1)
        self.assertEqual(flex['precio_total'], 15000)
        self.assertEqual(flex['comision_lbwus'], 2250)    # 15% de $15.000
        self.assertEqual(flex['monto_tutor'], 12750)      # 85% bruto tutor
        self.assertEqual(flex['comision_lbwus'] + flex['monto_tutor'], flex['precio_total'])

        # Progreso (4 clases @ $59.000)
        prog = PlanesService.calcular_precios_plan('progreso', tarifa_base=15000)
        self.assertEqual(prog['clases'], 4)
        self.assertEqual(prog['precio_total'], 59000)
        self.assertEqual(prog['comision_lbwus'], 8850)    # 15% de $59.000
        self.assertEqual(prog['monto_tutor'], 50150)      # 85% bruto tutor
        self.assertEqual(prog['comision_lbwus'] + prog['monto_tutor'], prog['precio_total'])

        # Intensivo (8 clases @ $116.000)
        inte = PlanesService.calcular_precios_plan('intensivo', tarifa_base=15000)
        self.assertEqual(inte['clases'], 8)
        self.assertEqual(inte['precio_total'], 116000)
        self.assertEqual(inte['comision_lbwus'], 17400)   # 15% de $116.000
        self.assertEqual(inte['monto_tutor'], 98600)      # 85% bruto tutor
        self.assertEqual(inte['comision_lbwus'] + inte['monto_tutor'], inte['precio_total'])

    def test_02_constantes_globales_de_liquidaciones(self):
        """Verifica que las constantes globales de liquidación estén sincronizadas con S4-03."""
        self.assertEqual(VALOR_INSCRIPCION, 15000)
        self.assertEqual(PAGO_PROFESOR, 12750)
        self.assertEqual(COMISION_LBWUS, 2250)
        self.assertEqual(PAGO_PROFESOR + COMISION_LBWUS, VALOR_INSCRIPCION)

    # -------------------------------------------------------------------------
    # 2. PRUEBAS DE TARIFAS VARIABLES POR TUTOR
    # -------------------------------------------------------------------------

    def test_03_tarifas_variables_por_tutor_proporcional(self):
        """Valida que un tutor con tarifa distinta ($20.000) mantenga la proporción y la comisión 15%."""
        planes = PlanesService.calcular_planes(profesor=self.profesor_var)
        self.assertEqual(len(planes), 3)

        # Plan Flexible con tarifa 20.000
        p_flex = planes[0]
        self.assertEqual(p_flex['precio_total'], 20000)
        self.assertEqual(p_flex['comision_lbwus'], 3000)  # 15% de 20.000
        self.assertEqual(p_flex['monto_tutor'], 17000)    # 85% de 20.000
        self.assertEqual(p_flex['comision_lbwus'] + p_flex['monto_tutor'], 20000)

        # Plan Progreso con tarifa 20.000: round(4 * 20000 * 59000 / 60000) = 78667
        p_prog = planes[1]
        self.assertEqual(p_prog['clases'], 4)
        self.assertTrue(p_prog['precio_total'] < 80000)  # Descuento aplicado
        self.assertEqual(p_prog['comision_lbwus'] + p_prog['monto_tutor'], p_prog['precio_total'])
        self.assertEqual(p_prog['comision_lbwus'], int(round(p_prog['precio_total'] * 0.15)))

        # Plan Intensivo con tarifa 20.000: round(8 * 20000 * 116000 / 120000) = 154667
        p_inte = planes[2]
        self.assertEqual(p_inte['clases'], 8)
        self.assertTrue(p_inte['precio_total'] < 160000)  # Descuento aplicado
        self.assertEqual(p_inte['comision_lbwus'] + p_inte['monto_tutor'], p_inte['precio_total'])

    # -------------------------------------------------------------------------
    # 3. CICLO DE VIDA DE PLAN_ALUMNO Y SALDO DE CLASES
    # -------------------------------------------------------------------------

    def test_04_creacion_de_plan_alumno_y_saldo_inicial(self):
        """Verifica la persistencia de un plan adquirido con sus clases acreditadas."""
        pago = Pago.objects.create(
            buy_order='LB-TEST-001',
            monto=59000,
            estado=Pago.ESTADO_PAGADA
        )

        plan = PlanesService.crear_plan_desde_pago(
            alumno=self.alumno,
            tipo_plan_str='progreso',
            pago=pago,
            profesor=self.profesor_ref
        )

        self.assertEqual(plan.tipo_plan, PlanAlumno.PLAN_PROGRESO)
        self.assertEqual(plan.total_clases, 4)
        self.assertEqual(plan.clases_disponibles, 4)
        self.assertEqual(plan.clases_consumidas, 0)
        self.assertEqual(plan.monto_total, 59000)
        self.assertEqual(plan.comision_lbwus, 8850)
        self.assertEqual(plan.monto_tutor, 50150)
        self.assertEqual(plan.estado, PlanAlumno.ESTADO_ACTIVO)
        self.assertTrue(plan.tiene_saldo)

    def test_05_consumo_progresivo_de_saldo_hasta_agotar(self):
        """Verifica el decremento de clases_disponibles y transición a estado 'agotado'."""
        pago = Pago.objects.create(
            buy_order='LB-TEST-002',
            monto=59000,
            estado=Pago.ESTADO_PAGADA
        )
        plan = PlanesService.crear_plan_desde_pago(
            alumno=self.alumno,
            tipo_plan_str='progreso',
            pago=pago,
            profesor=self.profesor_ref
        )

        # Consumir 3 clases
        for i in range(3):
            plan_consumido = PlanesService.consumir_clase_de_plan(alumno=self.alumno, profesor=self.profesor_ref)
            self.assertEqual(plan_consumido.pk, plan.pk)

        plan.refresh_from_db()
        self.assertEqual(plan.clases_disponibles, 1)
        self.assertEqual(plan.clases_consumidas, 3)
        self.assertEqual(plan.estado, PlanAlumno.ESTADO_ACTIVO)

        # Consumir la 4ta clase: pasa a agotado
        PlanesService.consumir_clase_de_plan(alumno=self.alumno, profesor=self.profesor_ref)
        plan.refresh_from_db()
        self.assertEqual(plan.clases_disponibles, 0)
        self.assertEqual(plan.clases_consumidas, 4)
        self.assertEqual(plan.estado, PlanAlumno.ESTADO_AGOTADO)
        self.assertFalse(plan.tiene_saldo)

        # Intentar consumir una 5ta clase debe lanzar PlanSinSaldoError
        with self.assertRaises(PlanSinSaldoError):
            PlanesService.consumir_clase_de_plan(alumno=self.alumno, profesor=self.profesor_ref)

    def test_06_reembolso_de_clase_restituye_saldo(self):
        """Verifica que reembolsar_clase devuelva saldo y reactive el plan si estaba agotado."""
        pago = Pago.objects.create(
            buy_order='LB-TEST-003',
            monto=15000,
            estado=Pago.ESTADO_PAGADA
        )
        plan = PlanesService.crear_plan_desde_pago(
            alumno=self.alumno,
            tipo_plan_str='flexible',
            pago=pago,
            profesor=self.profesor_ref
        )

        plan.consumir_clase()
        self.assertEqual(plan.estado, PlanAlumno.ESTADO_AGOTADO)

        plan.reembolsar_clase()
        self.assertEqual(plan.clases_disponibles, 1)
        self.assertEqual(plan.clases_consumidas, 0)
        self.assertEqual(plan.estado, PlanAlumno.ESTADO_ACTIVO)

    # -------------------------------------------------------------------------
    # 4. PRUEBAS DE LIQUIDACIÓN DOCENTE Y COBROS ANTICIPADOS
    # -------------------------------------------------------------------------

    def test_07_saldos_docente_con_comision_15_por_inscripcion(self):
        """El profesor recibe $12.750 disponible por inscripción individual pagada."""
        pago = Pago.objects.create(
            buy_order='LB-TEST-INS-01',
            monto=15000,
            estado=Pago.ESTADO_PAGADA
        )
        Inscripcion.objects.create(
            alumno=self.alumno,
            clase=self.clase,
            pago=pago,
            estado=Inscripcion.ESTADO_CONFIRMADA
        )

        saldos = calcular_saldos(self.profesor_ref)
        self.assertEqual(saldos['total_ganado'], 15000)
        self.assertEqual(saldos['disponible'], 12750)      # 85% tutor
        self.assertEqual(saldos['pendiente'], 2250)        # 15% comisión plataforma

    def test_08_proteccion_cobros_anticipados_en_planes(self):
        """
        Regla S4-03: No activar cobros anticipados.
        Un plan comprado no libera fondos a 'disponible' hasta que las clases se consumen/dictan.
        """
        pago = Pago.objects.create(
            buy_order='LB-TEST-PLAN-PROG',
            monto=59000,
            estado=Pago.ESTADO_PAGADA
        )
        plan = PlanesService.crear_plan_desde_pago(
            alumno=self.alumno,
            tipo_plan_str='progreso',
            pago=pago,
            profesor=self.profesor_ref
        )

        # 0 clases consumidas: $0 disponible, los $50.150 del tutor quedan protegidos en pendiente
        saldos_iniciales = calcular_saldos(self.profesor_ref)
        self.assertEqual(saldos_iniciales['total_ganado'], 59000)
        self.assertEqual(saldos_iniciales['disponible'], 0)
        self.assertEqual(saldos_iniciales['pendiente'], 59000)

        # Se consumen 2 de 4 clases: la mitad de los $50.150 se libera a disponible
        plan.consumir_clase()
        plan.consumir_clase()

        saldos_mitad = calcular_saldos(self.profesor_ref)
        esperado_disponible = int(round((50150 / 4) * 2))  # $25.075
        self.assertEqual(saldos_mitad['disponible'], esperado_disponible)
        self.assertEqual(saldos_mitad['total_ganado'], 59000)
        self.assertEqual(saldos_mitad['pendiente'], 59000 - esperado_disponible)

    # -------------------------------------------------------------------------
    # 5. AUSENCIA DE RENOVACIÓN AUTOMÁTICA Y CONDICIONES
    # -------------------------------------------------------------------------

    def test_09_sin_renovacion_automatica_en_planes(self):
        """Verifica que todos los planes se ofrezcan sin cobros recurrentes obligatorios."""
        planes = PlanesService.calcular_planes()
        for p in planes:
            self.assertTrue(p.get('sin_renovacion', False), f"El plan {p['nombre']} debe ser sin renovación obligatoria.")

    # -------------------------------------------------------------------------
    # 6. INTEGRACIÓN VISTA PÚBLICA DE PLANES (HTML Y JSON)
    # -------------------------------------------------------------------------

    def test_10_endpoint_planes_html_y_json(self):
        """Verifica la respuesta en HTML y en JSON del catálogo de planes."""
        # HTML
        url = reverse('planes')
        resp_html = self.client.get(url)
        self.assertEqual(resp_html.status_code, 200)
        self.assertContains(resp_html, 'Plan Flexible')
        self.assertContains(resp_html, 'Plan Progreso')
        self.assertContains(resp_html, 'Plan Intensivo')
        self.assertContains(resp_html, '$15.000')
        self.assertContains(resp_html, '$59.000')
        self.assertContains(resp_html, '$116.000')
        self.assertContains(resp_html, 'Sin renovación')

        # JSON API
        resp_json = self.client.get(url, {'format': 'json'})
        self.assertEqual(resp_json.status_code, 200)
        data = resp_json.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(len(data['planes']), 3)
        self.assertEqual(data['planes'][0]['precio_total'], 15000)
        self.assertEqual(data['planes'][1]['precio_total'], 59000)
        self.assertEqual(data['planes'][2]['precio_total'], 116000)
