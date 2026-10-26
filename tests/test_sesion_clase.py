"""
Pruebas exhaustivas para el modelo SesionClase, constraints de base de datos,
validaciones a nivel de modelo, QuerySets de disponibilidad, concurrencia y retrocompatibilidad.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import threading

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from alumnos.models import Alumno, Asignatura, Clase, Genero, Inscripcion, Profesor, SesionClase
from tests.test_paquetes import dar_paquete

User = get_user_model()


def crear_fixture_base():
    """Helper para generar género, alumno, profesor y clase base."""
    genero = Genero.objects.create(descripcion='Masculino')

    u_prof = User.objects.create_user(
        username='11111111-1',
        rut='11111111-1',
        first_name='Profesor Test',
        email='prof@lbwus.cl',
        password='password123',
        rol='profesor',
        genero=genero
    )
    profesor = Profesor.objects.create(
        user=u_prof,
        titulo_estado=Profesor.TITULO_APROBADO
    )

    u_alum1 = User.objects.create_user(
        username='22222222-2',
        rut='22222222-2',
        first_name='Alumno Uno',
        email='alum1@lbwus.cl',
        password='password123',
        rol='alumno',
        genero=genero
    )
    alumno1 = Alumno.objects.create(user=u_alum1)

    u_alum2 = User.objects.create_user(
        username='33333333-3',
        rut='33333333-3',
        first_name='Alumno Dos',
        email='alum2@lbwus.cl',
        password='password123',
        rol='alumno',
        genero=genero
    )
    alumno2 = Alumno.objects.create(user=u_alum2)

    asignatura = Asignatura.objects.create(nombre='Matemáticas Avanzadas')
    clase = Clase.objects.create(
        asignatura=asignatura,
        modalidad='online',
        horario=time(10, 0),
        profesor=profesor
    )

    # Reservar consume una clase de un paquete pagado: ambos alumnos tienen uno.
    for alumno in (alumno1, alumno2):
        dar_paquete(alumno, profesor, 'intensivo')

    return {
        'profesor': profesor,
        'alumno1': alumno1,
        'alumno2': alumno2,
        'asignatura': asignatura,
        'clase': clase,
    }


class SesionClaseValidacionesModelTests(TestCase):
    """Pruebas de validación en Python (clean(), full_clean(), propiedades)."""

    def setUp(self):
        f = crear_fixture_base()
        self.clase = f['clase']
        self.alumno1 = f['alumno1']

    def test_creacion_sesion_valida(self):
        inicio = timezone.now() + timedelta(days=2)
        fin = inicio + timedelta(hours=1, minutes=30)
        sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=inicio,
            fecha_hora_fin=fin,
            cupo_maximo=10,
            precio=Decimal('15000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )
        self.assertIsNotNone(sesion.pk)
        self.assertEqual(sesion.duracion_minutos, 90)
        self.assertEqual(sesion.cupos_disponibles, 10)
        self.assertEqual(sesion.cupos_ocupados, 0)
        self.assertTrue(sesion.esta_disponible)

    def test_rechaza_fecha_inicio_en_el_pasado_al_crear(self):
        pasado = timezone.now() - timedelta(days=1)
        sesion = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=pasado,
            fecha_hora_fin=pasado + timedelta(hours=1),
            cupo_maximo=5,
            precio=Decimal('10000.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            sesion.full_clean()
        self.assertIn('fecha_hora_inicio', ctx.exception.error_dict)

    def test_rechaza_fecha_fin_anterior_o_igual_a_inicio(self):
        inicio = timezone.now() + timedelta(days=2)
        sesion = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=inicio,
            fecha_hora_fin=inicio - timedelta(minutes=10),
            cupo_maximo=5,
            precio=Decimal('10000.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            sesion.full_clean()
        self.assertIn('fecha_hora_fin', ctx.exception.error_dict)

        # Mismo instante inicio == fin
        sesion.fecha_hora_fin = inicio
        with self.assertRaises(ValidationError) as ctx:
            sesion.full_clean()
        self.assertIn('fecha_hora_fin', ctx.exception.error_dict)

    def test_rechaza_cupo_maximo_menor_a_uno(self):
        inicio = timezone.now() + timedelta(days=2)
        sesion = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=inicio,
            fecha_hora_fin=inicio + timedelta(hours=1),
            cupo_maximo=0,
            precio=Decimal('10000.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            sesion.full_clean()
        self.assertIn('cupo_maximo', ctx.exception.error_dict)

    def test_rechaza_precio_negativo(self):
        inicio = timezone.now() + timedelta(days=2)
        sesion = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=inicio,
            fecha_hora_fin=inicio + timedelta(hours=1),
            cupo_maximo=5,
            precio=Decimal('-500.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            sesion.full_clean()
        self.assertIn('precio', ctx.exception.error_dict)


class SesionClaseCheckConstraintsDbTests(TestCase):
    """
    Pruebas que omiten la validación clean() para asegurar que la base de datos
    (PostgreSQL/SQLite) aplica sus CheckConstraints nativos.
    """

    def setUp(self):
        f = crear_fixture_base()
        self.clase = f['clase']

    def test_check_constraint_db_fin_posterior_a_inicio(self):
        inicio = timezone.now() + timedelta(days=3)
        sesion = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=inicio,
            fecha_hora_fin=inicio - timedelta(hours=1),
            cupo_maximo=5,
            precio=Decimal('10000.00')
        )
        with self.assertRaises(IntegrityError):
            sesion.save(skip_clean=True)

    def test_check_constraint_db_cupo_maximo_positivo(self):
        inicio = timezone.now() + timedelta(days=3)
        sesion = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=inicio,
            fecha_hora_fin=inicio + timedelta(hours=1),
            cupo_maximo=0,
            precio=Decimal('10000.00')
        )
        with self.assertRaises(IntegrityError):
            sesion.save(skip_clean=True)

    def test_check_constraint_db_precio_no_negativo(self):
        inicio = timezone.now() + timedelta(days=3)
        sesion = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=inicio,
            fecha_hora_fin=inicio + timedelta(hours=1),
            cupo_maximo=5,
            precio=Decimal('-1.00')
        )
        with self.assertRaises(IntegrityError):
            sesion.save(skip_clean=True)


class SesionClaseQuerySetTests(TestCase):
    """Pruebas para el QuerySet y Manager personalizado (disponibles, futuras, activas)."""

    def setUp(self):
        f = crear_fixture_base()
        self.clase = f['clase']
        self.profesor = f['profesor']
        self.alumno1 = f['alumno1']
        self.alumno2 = f['alumno2']

        # 1. Sesión futura disponible con cupos
        self.s_disponible = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() + timedelta(days=1),
            fecha_hora_fin=timezone.now() + timedelta(days=1, hours=1),
            cupo_maximo=5,
            precio=Decimal('15000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )

        # 2. Sesión futura llena (cupos agotados)
        self.s_llena = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() + timedelta(days=2),
            fecha_hora_fin=timezone.now() + timedelta(days=2, hours=1),
            cupo_maximo=1,
            precio=Decimal('20000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )
        Inscripcion.objects.create(alumno=self.alumno1, clase=self.clase, sesion=self.s_llena)

        # 3. Sesión cancelada
        self.s_cancelada = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() + timedelta(days=3),
            fecha_hora_fin=timezone.now() + timedelta(days=3, hours=1),
            cupo_maximo=5,
            precio=Decimal('15000.00'),
            estado=SesionClase.ESTADO_CANCELADA
        )

        # 4. Sesión pasada (creada con skip_clean)
        self.s_pasada = SesionClase(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() - timedelta(days=2),
            fecha_hora_fin=timezone.now() - timedelta(days=2, hours=-1),
            cupo_maximo=5,
            precio=Decimal('15000.00'),
            estado=SesionClase.ESTADO_FINALIZADA
        )
        self.s_pasada.save(skip_clean=True)

    def test_queryset_activas_excluye_canceladas(self):
        activas = SesionClase.objects.activas()
        self.assertIn(self.s_disponible, activas)
        self.assertIn(self.s_llena, activas)
        self.assertNotIn(self.s_cancelada, activas)

    def test_queryset_futuras_excluye_pasadas(self):
        futuras = SesionClase.objects.futuras()
        self.assertIn(self.s_disponible, futuras)
        self.assertIn(self.s_llena, futuras)
        self.assertNotIn(self.s_pasada, futuras)

    def test_queryset_disponibles_retorna_solo_sesiones_con_cupo_a_futuro(self):
        disponibles = list(SesionClase.objects.disponibles())
        self.assertIn(self.s_disponible, disponibles)
        self.assertNotIn(self.s_llena, disponibles, "Sesión con cupo lleno no debe figurar disponible")
        self.assertNotIn(self.s_cancelada, disponibles, "Sesión cancelada no debe figurar disponible")
        self.assertNotIn(self.s_pasada, disponibles, "Sesión pasada no debe figurar disponible")

    def test_queryset_filtro_por_profesor_y_asignatura(self):
        qs = SesionClase.objects.por_profesor(self.profesor)
        self.assertEqual(qs.count(), 4)
        qs_asig = SesionClase.objects.por_asignatura(self.clase.asignatura)
        self.assertEqual(qs_asig.count(), 4)


class SesionClaseReservasYConcurrenciaTests(TestCase):
    """Pruebas del método reservar() con integridad y control de sobrecupos."""

    def setUp(self):
        f = crear_fixture_base()
        self.clase = f['clase']
        self.alumno1 = f['alumno1']
        self.alumno2 = f['alumno2']

        self.sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() + timedelta(days=2),
            fecha_hora_fin=timezone.now() + timedelta(days=2, hours=1),
            cupo_maximo=1,  # Solo un cupo para verificar límite estricto
            precio=Decimal('18000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )

    def test_reserva_exitosa(self):
        inscripcion = self.sesion.reservar(self.alumno1)
        self.assertIsNotNone(inscripcion.pk)
        self.assertEqual(inscripcion.alumno, self.alumno1)
        self.assertEqual(inscripcion.sesion, self.sesion)
        self.assertEqual(inscripcion.clase, self.clase)
        self.assertEqual(self.sesion.cupos_ocupados, 1)
        self.assertEqual(self.sesion.cupos_disponibles, 0)
        self.assertFalse(self.sesion.esta_disponible)

    def test_reserva_duplicada_mismo_alumno_falla(self):
        self.sesion.cupo_maximo = 5
        self.sesion.save()
        self.sesion.reservar(self.alumno1)

        with self.assertRaises(ValidationError) as ctx:
            self.sesion.reservar(self.alumno1)
        self.assertIn('ya está inscrito', str(ctx.exception))

    def test_reserva_sin_cupos_falla_evitando_sobrecupo(self):
        # El alumno 1 toma el único cupo disponible
        self.sesion.reservar(self.alumno1)

        # El alumno 2 intenta reservar la misma sesión
        with self.assertRaises(ValidationError) as ctx:
            self.sesion.reservar(self.alumno2)
        self.assertIn('No quedan cupos disponibles', str(ctx.exception))

        # Verificar que el conteo en BD se mantuvo exactamente en 1
        self.assertEqual(self.sesion.inscripciones.count(), 1)

    def test_reserva_en_sesion_cancelada_o_finalizada_falla(self):
        self.sesion.estado = SesionClase.ESTADO_CANCELADA
        self.sesion.save()

        with self.assertRaises(ValidationError) as ctx:
            self.sesion.reservar(self.alumno1)
        self.assertIn('no se encuentra disponible para reservas', str(ctx.exception))


class ConcurrenciaSimuladaTests(TransactionTestCase):
    """
    Verifica que select_for_update() impida sobrecupos ante múltiples
    hilos intentando reservar concurrentemente el último cupo.
    """

    def setUp(self):
        f = crear_fixture_base()
        self.clase = f['clase']
        self.sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() + timedelta(days=1),
            fecha_hora_fin=timezone.now() + timedelta(days=1, hours=1),
            cupo_maximo=2,  # Solo 2 cupos para 4 solicitantes
            precio=Decimal('10000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )

        genero = Genero.objects.first()
        self.alumnos = []
        for i in range(4):
            u = User.objects.create_user(
                username=f'4444444{i}-4',
                rut=f'4444444{i}-4',
                email=f'c_alum{i}@lbwus.cl',
                password='pass',
                genero=genero
            )
            self.alumnos.append(Alumno.objects.create(user=u))
            dar_paquete(self.alumnos[-1], f['profesor'], 'intensivo')

    def test_reservas_sucesivas_respetan_cupo_maximo_estricto(self):
        """Verifica que solicitudes sucesivas se bloqueen al alcanzar el límite de cupos."""
        exitos = []
        errores = []

        for alumno in self.alumnos:
            try:
                self.sesion.reservar(alumno)
                exitos.append(alumno.pk)
            except ValidationError:
                errores.append(alumno.pk)

        # Exactamente 2 reservas exitosas y 2 rechazadas
        self.assertEqual(len(exitos), 2, "Deben haberse concretado exactamente 2 reservas")
        self.assertEqual(len(errores), 2, "Deben haber sido rechazadas exactamente 2 solicitudes por cupo lleno")
        self.assertEqual(Inscripcion.objects.filter(sesion=self.sesion).count(), 2)
        self.assertEqual(self.sesion.cupos_disponibles, 0)
        self.assertFalse(self.sesion.esta_disponible)


class RetrocompatibilidadInscripcionTests(TestCase):
    """Asegura que inscripciones preexistentes sin sesion sigan funcionando al 100%."""

    def setUp(self):
        f = crear_fixture_base()
        self.clase = f['clase']
        self.alumno1 = f['alumno1']
        self.sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() + timedelta(days=2),
            fecha_hora_fin=timezone.now() + timedelta(days=2, hours=1),
            cupo_maximo=5,
            precio=Decimal('10000.00')
        )

    def test_inscripcion_legada_sin_sesion_sigue_funcionando(self):
        # Como se hacía antes de SesionClase:
        ins = Inscripcion.objects.create(alumno=self.alumno1, clase=self.clase)
        self.assertIsNotNone(ins.pk)
        self.assertIsNone(ins.sesion)
        self.assertEqual(str(ins), f'{self.alumno1} inscrito en {self.clase}')

    def test_inscripcion_con_sesion_asigna_clase_automaticamente(self):
        ins = Inscripcion(alumno=self.alumno1, sesion=self.sesion)
        ins.save()
        self.assertEqual(ins.clase, self.clase)
        self.assertEqual(ins.sesion, self.sesion)
        self.assertIn(f'Sesión #{self.sesion.pk}', str(ins))

    def test_constraint_unique_impide_duplicado_mismo_alumno_y_sesion(self):
        Inscripcion.objects.create(alumno=self.alumno1, clase=self.clase, sesion=self.sesion)
        with self.assertRaises(IntegrityError):
            Inscripcion.objects.create(alumno=self.alumno1, clase=self.clase, sesion=self.sesion)


class VistasReservasSesionTests(TestCase):
    """Pruebas funcionales de los endpoints HTTP listar_sesiones_disponibles y reservar_sesion."""

    def setUp(self):
        f = crear_fixture_base()
        self.clase = f['clase']
        self.alumno1 = f['alumno1']
        self.alumno2 = f['alumno2']
        self.sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=timezone.now() + timedelta(days=2),
            fecha_hora_fin=timezone.now() + timedelta(days=2, hours=1),
            cupo_maximo=1,
            precio=Decimal('15000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )

    def test_listar_sesiones_disponibles_retorna_json(self):
        from django.urls import reverse
        resp = self.client.get(reverse('sesiones_disponibles'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['sesiones']), 1)
        item = data['sesiones'][0]
        self.assertEqual(item['id_sesion'], self.sesion.pk)
        self.assertEqual(item['cupos_disponibles'], 1)
        self.assertEqual(item['asignatura'], 'Matemáticas Avanzadas')

    def test_reservar_sesion_sin_autenticacion_rechazado(self):
        from django.urls import reverse
        resp = self.client.post(reverse('reservar_sesion'), {'id_sesion': self.sesion.pk})
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json()['success'])

    def test_reservar_sesion_exitoso_y_bloqueo_por_cupo_lleno(self):
        from django.urls import reverse
        # Autenticar alumno 1 en sesión
        session = self.client.session
        session['alumno_id'] = self.alumno1.pk
        session.save()

        # Reserva exitosa
        resp = self.client.post(
            reverse('reservar_sesion'),
            data={'id_sesion': self.sesion.pk},
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('Reserva confirmada con éxito', data['message'])
        self.assertTrue(Inscripcion.objects.filter(alumno=self.alumno1, sesion=self.sesion).exists())

        # Alumno 2 intenta reservar cuando cupo_maximo ya se alcanzó
        session = self.client.session
        session['alumno_id'] = self.alumno2.pk
        session.save()

        resp2 = self.client.post(
            reverse('reservar_sesion'),
            data={'id_sesion': self.sesion.pk},
            content_type='application/json'
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertFalse(data2['success'])
        self.assertIn('No quedan cupos disponibles', data2['message'])
