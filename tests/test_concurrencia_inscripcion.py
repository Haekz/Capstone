"""
Suite de Pruebas de Blindaje Transaccional y Concurrencia para Inscripciones y Reservas.
Verifica:
1. Caso Válido: Inscripción exitosa con decremento o cálculo correcto de cupo disponible.
2. Caso Duplicado: Comprobar que un segundo intento de inscripción arroje InscripcionDuplicadaError
   e impida el guardado por constraint de BD.
3. Forzado de UniqueConstraint en base de datos al eludir la capa de servicio (IntegrityError).
4. Caso Sin Cupo: Comprobar que si el cupo está agotado, se rechace la transacción con CupoAgotadoError.
5. Re-inscripción tras Cancelación: Comprobar que si se cancela la inscripción previa, el constraint
   permite inscribirse nuevamente y el cupo se libera de inmediato.
6. Inscripción a Clase General: Prevenir inscripciones duplicadas en clases sin sesión puntual.
7. Test de Concurrencia Multihilo: Simular peticiones simultáneas superando el cupo para verificar
   que exactamente el número máximo de alumnos obtenga cupo y el resto sea rechazado limpiamente.
"""
from datetime import time, timedelta
from decimal import Decimal
from time import sleep
from unittest.mock import patch
import threading

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import (
    Alumno, Asignatura, Clase, Genero,
    Inscripcion, PaqueteClases, Profesor, SesionClase
)
from alumnos.services import InscripcionService
from tests.test_paquetes import dar_paquete
from alumnos.exceptions import (
    InscripcionError,
    CupoAgotadoError,
    InscripcionDuplicadaError,
    SesionNoDisponibleError,
    SinClasesDisponiblesError,
)

User = get_user_model()

# Produccion usa PostgreSQL: ahi select_for_update bloquea filas de verdad y el
# resultado de una carrera debe ser exacto. SQLite bloquea la base entera y algunos
# hilos fallan con 'database is locked', asi que en SQLite solo se exige no sobrepasar.
ES_POSTGRES = connection.vendor == 'postgresql'


def en_paralelo(tarea, argumentos):
    """Corre tarea(argumento) en un hilo por argumento, todos largando a la vez.

    Devuelve (exitos, rechazos, otros): rechazos son InscripcionError (sin cupo,
    sin clases...); otros, cualquier otra excepcion.
    """
    exitos, rechazos, otros = [], [], []
    largada = threading.Barrier(len(argumentos))

    def correr(argumento):
        try:
            largada.wait()
            tarea(argumento)
            exitos.append(argumento)
        except InscripcionError as exc:
            rechazos.append(exc)
        except Exception as exc:
            otros.append(exc)
        finally:
            connection.close()  # cada hilo abre su propia conexion

    hilos = [threading.Thread(target=correr, args=(argumento,)) for argumento in argumentos]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return exitos, rechazos, otros


class TestBlindajeTransaccionalInscripcion(TestCase):
    """Pruebas unitarias de lógica transaccional y validaciones de dominio."""

    def setUp(self):
        self.genero = Genero.objects.create(descripcion='Masculino')

        self.u_prof = User.objects.create_user(
            username='15333444-5',
            rut='15333444-5',
            first_name='Alan',
            last_name='Turing',
            email='alan@test.cl',
            password='Password123!',
            rol='profesor',
            genero=self.genero
        )
        self.profesor = Profesor.objects.create(
            user=self.u_prof,
            titulo_estado=Profesor.TITULO_APROBADO
        )

        self.asignatura = Asignatura.objects.create(nombre='Algoritmos y Concurrencia')

        self.clase = Clase.objects.create(
            profesor=self.profesor,
            asignatura=self.asignatura,
            modalidad='online',
            horario=time(10, 0)
        )

        # Alumnos de prueba
        self.alumnos = []
        for i in range(1, 6):
            rut_val = f'2000000{i}-0'
            u_al = User.objects.create_user(
                username=rut_val,
                rut=rut_val,
                email=f'alumno_{i}@test.cl',
                password='Password123!',
                first_name=f'Estudiante_{i}',
                last_name='Test',
                rol='alumno',
                genero=self.genero
            )
            alumno = Alumno.objects.create(user=u_al)
            self.alumnos.append(alumno)
            dar_paquete(alumno, self.profesor, 'intensivo')  # reservar consume una clase pagada

        # Sesión con cupo limitado de 2 plazas
        self.ahora = timezone.now()
        self.sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=self.ahora + timedelta(days=2),
            fecha_hora_fin=self.ahora + timedelta(days=2, hours=2),
            cupo_maximo=2,
            precio=Decimal('15000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )

    def test_01_caso_valido_inscripcion_decrementa_cupos(self):
        """Caso Válido: Una inscripción exitosa calcula y decrementa correctamente el cupo disponible."""
        self.assertEqual(self.sesion.cupos_disponibles, 2)
        self.assertEqual(self.sesion.cupos_ocupados, 0)

        inscripcion = InscripcionService.inscribir_alumno_en_sesion(
            alumno=self.alumnos[0],
            sesion_id=self.sesion.pk
        )

        self.assertIsNotNone(inscripcion.pk)
        self.assertEqual(inscripcion.estado, Inscripcion.ESTADO_CONFIRMADA)
        self.assertEqual(inscripcion.alumno, self.alumnos[0])
        self.assertEqual(inscripcion.sesion, self.sesion)

        # Re-evaluar sesión en BD
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.cupos_ocupados, 1)
        self.assertEqual(self.sesion.cupos_disponibles, 1)

    def test_02_caso_duplicado_eleva_inscripcion_duplicada_error(self):
        """Caso Duplicado: Un segundo intento de inscripción arroja InscripcionDuplicadaError."""
        InscripcionService.inscribir_alumno_en_sesion(self.alumnos[0], self.sesion.pk)

        with self.assertRaises(InscripcionDuplicadaError) as ctx:
            InscripcionService.inscribir_alumno_en_sesion(self.alumnos[0], self.sesion.pk)

        self.assertIn('ya está inscrito', str(ctx.exception).lower())
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.cupos_ocupados, 1)

    def test_03_forzado_unique_constraint_en_base_de_datos(self):
        """
        Si se intenta eludir el servicio e insertar directamente vía ORM/SQL,
        el UniqueConstraint en PostgreSQL/SQLite dispara IntegrityError.
        """
        Inscripcion.objects.create(
            alumno=self.alumnos[0],
            clase=self.clase,
            sesion=self.sesion,
            estado=Inscripcion.ESTADO_CONFIRMADA
        )

        with self.assertRaises(IntegrityError):
            Inscripcion.objects.create(
                alumno=self.alumnos[0],
                clase=self.clase,
                sesion=self.sesion,
                estado=Inscripcion.ESTADO_CONFIRMADA
            )

    def test_04_caso_sin_cupo_eleva_cupo_agotado_error(self):
        """Caso Sin Cupo: Al completarse el cupo máximo, solicitudes adicionales son rechazadas con CupoAgotadoError."""
        # Ocupar los 2 cupos disponibles
        InscripcionService.inscribir_alumno_en_sesion(self.alumnos[0], self.sesion.pk)
        InscripcionService.inscribir_alumno_en_sesion(self.alumnos[1], self.sesion.pk)

        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.cupos_disponibles, 0)

        # Tercer intento debe ser rechazado sin alterar cupos
        with self.assertRaises(CupoAgotadoError) as ctx:
            InscripcionService.inscribir_alumno_en_sesion(self.alumnos[2], self.sesion.pk)

        self.assertIn('no quedan cupos', str(ctx.exception).lower())
        self.assertEqual(self.sesion.inscripciones.count(), 2)

    def test_05_cancelar_inscripcion_libera_cupo_y_permite_reinscripcion(self):
        """Al cancelar una inscripción, el cupo se libera y el constraint condicional permite re-inscribirse."""
        insc = InscripcionService.inscribir_alumno_en_sesion(self.alumnos[0], self.sesion.pk)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.cupos_disponibles, 1)

        InscripcionService.cancelar_inscripcion(self.alumnos[0], insc.pk)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.cupos_disponibles, 2)
        self.assertEqual(self.sesion.cupos_ocupados, 0)

        # El mismo alumno puede volver a inscribirse
        reinscripcion = InscripcionService.inscribir_alumno_en_sesion(self.alumnos[0], self.sesion.pk)
        self.assertEqual(reinscripcion.estado, Inscripcion.ESTADO_CONFIRMADA)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.cupos_ocupados, 1)

    def test_06_inscripcion_clase_general_unique_constraint(self):
        """Para clases generales sin sesión puntual, el constraint evita duplicados."""
        insc1 = InscripcionService.inscribir_alumno_en_clase(self.alumnos[0], self.clase.pk)
        self.assertIsNotNone(insc1.pk)
        self.assertIsNone(insc1.sesion)

        with self.assertRaises(InscripcionDuplicadaError):
            InscripcionService.inscribir_alumno_en_clase(self.alumnos[0], self.clase.pk)


class TestConcurrenciaMultihiloInscripcion(TransactionTestCase):
    """
    Prueba de estrés de concurrencia usando TransactionTestCase (permite commits reales y multi-threading).
    Verifica que bajo condiciones de carrera simultáneas nunca se sobrepase el cupo máximo (select_for_update).
    """

    def setUp(self):
        self.genero = Genero.objects.create(descripcion='Femenino')

        self.u_prof = User.objects.create_user(
            username='16111222-3',
            rut='16111222-3',
            first_name='Ada',
            last_name='Lovelace',
            email='ada@test.cl',
            password='Password123!',
            rol='profesor',
            genero=self.genero
        )
        self.profesor = Profesor.objects.create(
            user=self.u_prof,
            titulo_estado=Profesor.TITULO_APROBADO
        )

        self.asignatura = Asignatura.objects.create(nombre='Sistemas Concurrentes')

        self.clase = Clase.objects.create(
            profesor=self.profesor,
            asignatura=self.asignatura,
            modalidad='online',
            horario=time(14, 0)
        )

        # Crear 6 alumnos competidores
        self.alumnos = []
        for i in range(1, 7):
            rut_val = f'2100000{i}-0'
            u_al = User.objects.create_user(
                username=rut_val,
                rut=rut_val,
                email=f'thread_{i}@test.cl',
                password='Password123!',
                first_name=f'ThreadAlumno_{i}',
                last_name='Test',
                rol='alumno',
                genero=self.genero
            )
            alumno = Alumno.objects.create(user=u_al)
            self.alumnos.append(alumno)
            dar_paquete(alumno, self.profesor, 'intensivo')  # reservar consume una clase pagada

        # Sesión estricta con cupo = 2 para 6 solicitantes simultáneos
        self.ahora = timezone.now()
        self.sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=self.ahora + timedelta(days=3),
            fecha_hora_fin=self.ahora + timedelta(days=3, hours=1),
            cupo_maximo=2,
            precio=Decimal('20000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )

    def test_concurrencia_exacta_sin_sobrecupo(self):
        """
        6 hilos concurrentes intentan reservar simultaneamente una sesion con cupo_maximo = 2.
        Nunca hay sobrecupo; en PostgreSQL exactamente 2 entran y 4 reciben CupoAgotadoError.
        """
        exitos, rechazos, otros = en_paralelo(
            lambda alumno: InscripcionService.inscribir_alumno_en_sesion(alumno, self.sesion.pk),
            self.alumnos,
        )

        total_en_bd = Inscripcion.objects.filter(
            sesion=self.sesion,
            estado=Inscripcion.ESTADO_CONFIRMADA
        ).count()

        self.assertLessEqual(
            total_en_bd, self.sesion.cupo_maximo,
            f"Sobrecupo detectado: hay {total_en_bd} inscripciones en BD cuando el cupo máximo es {self.sesion.cupo_maximo}"
        )
        self.assertEqual(len(exitos), total_en_bd)
        self.assertEqual(len(exitos) + len(rechazos) + len(otros), 6)
        if ES_POSTGRES:
            self.assertEqual(otros, [])
            self.assertEqual(len(exitos), 2)
            self.assertEqual([type(exc) for exc in rechazos], [CupoAgotadoError] * 4)

    def test_ultima_clase_del_paquete_no_se_gasta_dos_veces(self):
        """Dos reservas simultaneas del mismo alumno, en sesiones distintas, por su ultima clase.

        El cupo no las frena (son sesiones distintas): solo el bloqueo del paquete.
        """
        alumno = self.alumnos[0]
        alumno.paquetes.update(clases=1)
        otra_sesion = SesionClase.objects.create(
            clase=self.clase,
            fecha_hora_inicio=self.ahora + timedelta(days=4),
            fecha_hora_fin=self.ahora + timedelta(days=4, hours=1),
            cupo_maximo=2,
            precio=Decimal('20000.00'),
            estado=SesionClase.ESTADO_PROGRAMADA
        )

        contar = PaqueteClases.clases_disponibles.fget

        def contar_lento(paquete):
            disponibles = contar(paquete)
            sleep(0.3)  # ensancha la carrera: sin bloqueo, ambos hilos leerian "1 libre"
            return disponibles

        with patch.object(PaqueteClases, 'clases_disponibles', property(contar_lento)):
            exitos, rechazos, otros = en_paralelo(
                lambda sesion: InscripcionService.inscribir_alumno_en_sesion(alumno, sesion.pk),
                [self.sesion, otra_sesion],
            )

        self.assertLessEqual(len(exitos), 1, 'Se gasto dos veces la misma clase del paquete')
        self.assertEqual(Inscripcion.objects.filter(alumno=alumno).count(), len(exitos))
        if ES_POSTGRES:
            self.assertEqual(otros, [])
            self.assertEqual(len(exitos), 1)
            self.assertEqual([type(exc) for exc in rechazos], [SinClasesDisponiblesError])


class TestFiltrosSesionClase(TestCase):
    """Pruebas automatizadas de filtros por asignatura, profesor, disponibilidad temporal y cupos."""

    def setUp(self):
        self.client = Client()
        self.genero = Genero.objects.create(descripcion='Femenino')

        # Profesor 1
        self.u_prof1 = User.objects.create_user(
            username='17000001-1', rut='17000001-1', email='prof1@test.cl',
            password='Password123!', rol='profesor', genero=self.genero,
            first_name='Profesor', last_name='Uno'
        )
        self.prof1 = Profesor.objects.create(user=self.u_prof1, titulo_estado=Profesor.TITULO_APROBADO)

        # Profesor 2
        self.u_prof2 = User.objects.create_user(
            username='17000002-2', rut='17000002-2', email='prof2@test.cl',
            password='Password123!', rol='profesor', genero=self.genero,
            first_name='Profesor', last_name='Dos'
        )
        self.prof2 = Profesor.objects.create(user=self.u_prof2, titulo_estado=Profesor.TITULO_APROBADO)

        # Asignaturas
        self.asig1 = Asignatura.objects.create(nombre='Álgebra Lineal')
        self.asig2 = Asignatura.objects.create(nombre='Química Orgánica')

        # Clases
        self.clase1 = Clase.objects.create(
            profesor=self.prof1, asignatura=self.asig1, modalidad='online', horario=time(9, 0)
        )
        self.clase2 = Clase.objects.create(
            profesor=self.prof2, asignatura=self.asig2, modalidad='presencial', horario=time(11, 0)
        )

        # Alumno
        self.u_alum = User.objects.create_user(
            username='18000001-1', rut='18000001-1', email='alum_filtro@test.cl',
            password='Password123!', rol='alumno', genero=self.genero,
            first_name='Estudiante', last_name='Filtros'
        )
        self.alumno = Alumno.objects.create(user=self.u_alum)

        self.ahora = timezone.now()

        # s1: Futura, programada, con cupo (Clase 1)
        self.s1 = SesionClase.objects.create(
            clase=self.clase1,
            fecha_hora_inicio=self.ahora + timedelta(days=2),
            fecha_hora_fin=self.ahora + timedelta(days=2, hours=1),
            cupo_maximo=5, precio=Decimal('10000.00'), estado=SesionClase.ESTADO_PROGRAMADA
        )

        # s2: Futura, programada, pero con CUPO LLENO (Clase 1)
        self.s2 = SesionClase.objects.create(
            clase=self.clase1,
            fecha_hora_inicio=self.ahora + timedelta(days=3),
            fecha_hora_fin=self.ahora + timedelta(days=3, hours=1),
            cupo_maximo=1, precio=Decimal('12000.00'), estado=SesionClase.ESTADO_PROGRAMADA
        )
        Inscripcion.objects.create(
            alumno=self.alumno, clase=self.clase1, sesion=self.s2, estado=Inscripcion.ESTADO_CONFIRMADA
        )

        # s3: PASADA (fecha_hora_inicio en el pasado)
        self.s3 = SesionClase(
            clase=self.clase1,
            fecha_hora_inicio=self.ahora - timedelta(days=2),
            fecha_hora_fin=self.ahora - timedelta(days=2, hours=-1),
            cupo_maximo=5, precio=Decimal('10000.00'), estado=SesionClase.ESTADO_PROGRAMADA
        )
        self.s3.save(skip_clean=True)

        # s4: Futura pero CANCELADA (Clase 2)
        self.s4 = SesionClase.objects.create(
            clase=self.clase2,
            fecha_hora_inicio=self.ahora + timedelta(days=4),
            fecha_hora_fin=self.ahora + timedelta(days=4, hours=1),
            cupo_maximo=5, precio=Decimal('14000.00'), estado=SesionClase.ESTADO_CANCELADA
        )

        # s5: Futura, programada, con cupo (Clase 2)
        self.s5 = SesionClase.objects.create(
            clase=self.clase2,
            fecha_hora_inicio=self.ahora + timedelta(days=5),
            fecha_hora_fin=self.ahora + timedelta(days=5, hours=1),
            cupo_maximo=8, precio=Decimal('15000.00'), estado=SesionClase.ESTADO_PROGRAMADA
        )

    def test_01_filtro_disponibles_excluye_llenas_pasadas_y_canceladas(self):
        """SesionClase.objects.disponibles() solo debe incluir sesiones futuras, programadas y con cupos."""
        disponibles = list(SesionClase.objects.disponibles())
        self.assertIn(self.s1, disponibles)
        self.assertIn(self.s5, disponibles)
        self.assertNotIn(self.s2, disponibles, "Sesión con cupo agotado no debe estar en disponibles")
        self.assertNotIn(self.s3, disponibles, "Sesión con fecha pasada no debe estar en disponibles")
        self.assertNotIn(self.s4, disponibles, "Sesión cancelada no debe estar en disponibles")

    def test_02_filtro_por_asignatura(self):
        """SesionClase.objects.por_asignatura() debe discriminar exactamente por materia."""
        sesiones_asig1 = list(SesionClase.objects.por_asignatura(self.asig1))
        self.assertEqual(len(sesiones_asig1), 3)
        self.assertIn(self.s1, sesiones_asig1)
        self.assertIn(self.s2, sesiones_asig1)
        self.assertIn(self.s3, sesiones_asig1)
        self.assertNotIn(self.s5, sesiones_asig1)

    def test_03_filtro_por_profesor(self):
        """SesionClase.objects.por_profesor() debe discriminar exactamente por docente."""
        sesiones_prof2 = list(SesionClase.objects.por_profesor(self.prof2))
        self.assertEqual(len(sesiones_prof2), 2)
        self.assertIn(self.s4, sesiones_prof2)
        self.assertIn(self.s5, sesiones_prof2)
        self.assertNotIn(self.s1, sesiones_prof2)

    def test_04_api_listar_sesiones_con_filtro_clase_id(self):
        """El endpoint /alumnos/api/sesiones/?clase_id=X retorna solo sesiones disponibles de esa clase."""
        resp = self.client.get(reverse('sesiones_disponibles'), {'clase_id': self.clase1.pk})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        ids = [item['id_sesion'] for item in data['sesiones']]
        self.assertIn(self.s1.pk, ids)
        self.assertNotIn(self.s5.pk, ids)

    def test_05_api_listar_sesiones_marca_ya_inscrito_correctamente(self):
        """Si un alumno autenticado consulta sesiones, ya_inscrito debe reflejar su estado."""
        # Inscribir a alumno en s1
        Inscripcion.objects.create(
            alumno=self.alumno, clase=self.clase1, sesion=self.s1, estado=Inscripcion.ESTADO_CONFIRMADA
        )

        session = self.client.session
        session['alumno_id'] = self.alumno.pk
        session.save()

        resp = self.client.get(reverse('sesiones_disponibles'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        items = {item['id_sesion']: item['ya_inscrito'] for item in data['sesiones']}
        self.assertTrue(items.get(self.s1.pk))
        self.assertFalse(items.get(self.s5.pk))


class TestSeguridadReservasYControlAcceso(TestCase):
    """Pruebas de seguridad contra sesiones no autorizadas, IDOR y validación de permisos en reservas."""

    def setUp(self):
        self.client = Client()
        self.genero = Genero.objects.create(descripcion='Masculino')

        # Docente con título aprobado
        self.u_prof_ok = User.objects.create_user(
            username='19000001-1', rut='19000001-1', email='prof_ok@test.cl',
            password='Password123!', rol='profesor', genero=self.genero
        )
        self.prof_ok = Profesor.objects.create(user=self.u_prof_ok, titulo_estado=Profesor.TITULO_APROBADO)

        # Docente sin título aprobado (pendiente)
        self.u_prof_no = User.objects.create_user(
            username='19000002-2', rut='19000002-2', email='prof_no@test.cl',
            password='Password123!', rol='profesor', genero=self.genero
        )
        self.prof_no = Profesor.objects.create(user=self.u_prof_no, titulo_estado=Profesor.TITULO_PENDIENTE)

        self.asig = Asignatura.objects.create(nombre='Cálculo de Seguridad')

        self.clase_ok = Clase.objects.create(
            profesor=self.prof_ok, asignatura=self.asig, modalidad='online', horario=time(10, 0)
        )
        self.clase_no = Clase.objects.create(
            profesor=self.prof_no, asignatura=self.asig, modalidad='online', horario=time(10, 0)
        )

        # Alumno 1 (Víctima)
        self.u_alum1 = User.objects.create_user(
            username='19000003-3', rut='19000003-3', email='alum1@test.cl',
            password='Password123!', rol='alumno', genero=self.genero
        )
        self.alumno1 = Alumno.objects.create(user=self.u_alum1)

        # Alumno 2 (Atacante / Tercero)
        self.u_alum2 = User.objects.create_user(
            username='19000004-4', rut='19000004-4', email='alum2@test.cl',
            password='Password123!', rol='alumno', genero=self.genero
        )
        self.alumno2 = Alumno.objects.create(user=self.u_alum2)

        self.ahora = timezone.now()
        self.sesion = SesionClase.objects.create(
            clase=self.clase_ok,
            fecha_hora_inicio=self.ahora + timedelta(days=2),
            fecha_hora_fin=self.ahora + timedelta(days=2, hours=1),
            cupo_maximo=5, precio=Decimal('10000.00'), estado=SesionClase.ESTADO_PROGRAMADA
        )

    def test_01_reserva_anonima_retorna_401(self):
        """Un usuario sin sesión activa de alumno no puede reservar y recibe HTTP 401."""
        resp = self.client.post(
            reverse('reservar_sesion'),
            data={'id_sesion': self.sesion.pk}
        )
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json()['success'])

    def test_02_reserva_metodo_get_no_permitido_405(self):
        """Peticiones GET al endpoint de reserva reciben HTTP 405 Method Not Allowed."""
        session = self.client.session
        session['alumno_id'] = self.alumno1.pk
        session.save()

        resp = self.client.get(reverse('reservar_sesion'))
        self.assertEqual(resp.status_code, 405)

    def test_03_reserva_sin_id_retorna_400(self):
        """Petición POST sin id_sesion retorna HTTP 400 Bad Request."""
        session = self.client.session
        session['alumno_id'] = self.alumno1.pk
        session.save()

        resp = self.client.post(reverse('reservar_sesion'), data={})
        self.assertEqual(resp.status_code, 400)

    def test_04_reserva_sesion_inexistente_retorna_404(self):
        """Petición con id_sesion que no existe en BD retorna HTTP 404."""
        session = self.client.session
        session['alumno_id'] = self.alumno1.pk
        session.save()

        resp = self.client.post(reverse('reservar_sesion'), data={'id_sesion': 99999})
        self.assertEqual(resp.status_code, 404)

    def test_05_reserva_profesor_sin_titulo_rechazada(self):
        """Intento de reserva para una clase cuyo profesor no está validado es rechazado."""
        sesion_prof_no = SesionClase.objects.create(
            clase=self.clase_no,
            fecha_hora_inicio=self.ahora + timedelta(days=2),
            fecha_hora_fin=self.ahora + timedelta(days=2, hours=1),
            cupo_maximo=5, precio=Decimal('10000.00'), estado=SesionClase.ESTADO_PROGRAMADA
        )

        session = self.client.session
        session['alumno_id'] = self.alumno1.pk
        session.save()

        resp = self.client.post(
            reverse('reservar_sesion'),
            data={'id_sesion': sesion_prof_no.pk}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('título validado', data['message'])

    def test_06_seguridad_idor_cancelar_inscripcion_ajena_bloqueada(self):
        """Un alumno no puede cancelar la inscripción de otro alumno (Protección IDOR)."""
        inscripcion_victima = Inscripcion.objects.create(
            alumno=self.alumno1,
            clase=self.clase_ok,
            sesion=self.sesion,
            estado=Inscripcion.ESTADO_CONFIRMADA
        )

        # Iniciar sesión como alumno 2 (atacante)
        self.client.force_login(self.u_alum2)
        session = self.client.session
        session['alumno_id'] = self.alumno2.pk
        session.save()

        # Intentar cancelar la inscripción de alumno 1
        resp = self.client.get(
            reverse('cancelar_inscripcion', args=[inscripcion_victima.pk])
        )
        # Debe ser rechazado con 404 porque no pertenece al alumno en sesión
        self.assertEqual(resp.status_code, 404)

        # Verificar que la inscripción de la víctima sigue intacta
        inscripcion_victima.refresh_from_db()
        self.assertEqual(inscripcion_victima.estado, Inscripcion.ESTADO_CONFIRMADA)

