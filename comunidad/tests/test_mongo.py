"""Pruebas rapidas de la base tecnica de MongoDB (mongomock, sin red)."""

from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from alumnos.models import Tutor
from comunidad import esquemas, mongo

from .base import MongoTestCase

User = get_user_model()

# La URI real se exporta al activar el entorno: estas pruebas la anulan.
SIN_MONGO = override_settings(MONGODB_URI=None)


@SIN_MONGO
class SinConfiguracionTests(TestCase):
    def setUp(self):
        mongo.restablecer()

    def tearDown(self):
        mongo.restablecer()

    def test_get_client_sin_uri_lanza_mongo_no_configurado(self):
        with self.assertRaises(mongo.MongoNoConfigurado):
            mongo.get_client()

    def test_disponible_sin_uri_devuelve_false_sin_lanzar(self):
        self.assertFalse(mongo.disponible())

    def test_mongo_init_sin_uri_termina_con_error(self):
        with self.assertRaises(CommandError):
            call_command('mongo_init', stdout=StringIO())


class ClienteTests(MongoTestCase):
    def test_coleccion_desconocida_lanza_value_error(self):
        with self.assertRaises(ValueError):
            mongo.coleccion('inexistente')

    def test_coleccion_conocida_usa_la_base_inyectada(self):
        col = mongo.coleccion('actividad')
        self.assertEqual(col.database.name, 'lbwus_test')

    def test_ping_devuelve_latencia(self):
        self.assertGreaterEqual(mongo.ping(), 0)
        self.assertTrue(mongo.disponible())

    def test_disponible_con_error_de_red_devuelve_false(self):
        with mock.patch.object(mongo, 'ping',
                               side_effect=ServerSelectionTimeoutError('x')):
            self.assertFalse(mongo.disponible())

    def test_se_crean_todos_los_indices_declarados(self):
        db = mongo.get_db()
        for nombre, definicion in esquemas.COLECCIONES.items():
            with self.subTest(coleccion=nombre):
                esperados = {i.document['name'] for i in definicion['indices']}
                creados = set(db[nombre].index_information())
                self.assertTrue(esperados <= creados, esperados - creados)

    def test_ttl_de_actividad_es_de_180_dias(self):
        info = mongo.coleccion('actividad').index_information()
        self.assertEqual(info['ttl_fecha']['expireAfterSeconds'],
                         180 * 24 * 3600)

    def test_crear_indices_es_idempotente(self):
        esquemas.crear_indices(mongo.get_db())

    def test_resena_unica_por_inscripcion(self):
        resenas = mongo.coleccion('resenas')
        doc = {'profesor_id': 1, 'alumno_id': 2, 'puntaje': 5, 'visible': True}
        resenas.insert_one({**doc, 'inscripcion_id': 21})
        with self.assertRaises(DuplicateKeyError):
            resenas.insert_one({**doc, 'inscripcion_id': 21})

    def test_conversacion_unica_por_alumno_y_profesor(self):
        conversaciones = mongo.coleccion('conversaciones')
        conversaciones.insert_one({'alumno_id': 7, 'profesor_id': 3})
        conversaciones.insert_one({'alumno_id': 7, 'profesor_id': 4})
        with self.assertRaises(DuplicateKeyError):
            conversaciones.insert_one({'alumno_id': 7, 'profesor_id': 3})


class SaludTests(MongoTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_admin = User.objects.create_user('10101010-1', password='clave12345')
        cls.tutor = Tutor.objects.create(user=cls.user_admin)

    def _entrar_como_admin(self):
        self.client.force_login(self.user_admin)
        sesion = self.client.session
        sesion['admin_id'] = self.tutor.id_tutor
        sesion.save()

    def _get(self):
        respuesta = self.client.get(reverse('comunidad_salud'))
        self.assertNotIn(b'mongodb+srv', respuesta.content)
        return respuesta

    def test_anonimo_no_entra(self):
        self.assertFalse(self._get().json()['success'])

    def test_admin_con_mongo_disponible(self):
        self._entrar_como_admin()
        respuesta = self._get()
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos['mongodb'], 'ok')
        self.assertEqual(datos['base'], 'lbwus_test')
        self.assertIn('latencia_ms', datos)

    @override_settings(MONGODB_URI=None)
    def test_admin_sin_configuracion(self):
        mongo.restablecer()
        self._entrar_como_admin()
        respuesta = self._get()
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json(), {'mongodb': 'no_configurado'})

    def test_admin_con_error_no_muestra_el_mensaje(self):
        self._entrar_como_admin()
        error = ServerSelectionTimeoutError('mongodb+srv://u:clave@host')
        with mock.patch.object(mongo, 'ping', side_effect=error):
            respuesta = self._get()
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json(), {
            'mongodb': 'error', 'detalle': 'ServerSelectionTimeoutError',
        })

    def test_post_no_permitido(self):
        self._entrar_como_admin()
        respuesta = self.client.post(reverse('comunidad_salud'))
        self.assertEqual(respuesta.status_code, 405)


class MongoInitTests(MongoTestCase):
    def _ejecutar(self, *args):
        salida = StringIO()
        call_command('mongo_init', *args, stdout=salida)
        return salida.getvalue()

    def test_verificar_muestra_base_y_latencia(self):
        salida = self._ejecutar('--verificar')
        self.assertIn('lbwus_test', salida)
        self.assertIn('latencia', salida)

    def test_inicializa_y_es_idempotente(self):
        # mongomock no soporta validadores: se simulan; los indices son reales.
        with mock.patch.object(esquemas, 'aplicar_validadores', return_value={
            nombre: 'creado' for nombre in esquemas.COLECCIONES
        }):
            primera = self._ejecutar()
            self._ejecutar()
        for nombre in esquemas.COLECCIONES:
            self.assertIn(nombre, primera)
        self.assertIn('inscripcion_unica', primera)

    def test_error_de_red_no_muestra_el_mensaje(self):
        error = ServerSelectionTimeoutError('mongodb+srv://u:clave@host')
        with mock.patch.object(mongo, 'ping', side_effect=error):
            with self.assertRaises(CommandError) as ctx:
                self._ejecutar()
        self.assertNotIn('mongodb+srv', str(ctx.exception))

    def test_base_prod_pide_confirmacion(self):
        mongo.usar_cliente(mongo.get_client(), db='lbwus_prod')
        with mock.patch.object(esquemas, 'aplicar_validadores') as aplicar, \
                mock.patch('builtins.input', return_value='no'):
            with self.assertRaises(CommandError):
                self._ejecutar()
        aplicar.assert_not_called()

    def test_base_prod_con_si_no_pregunta(self):
        mongo.usar_cliente(mongo.get_client(), db='lbwus_prod')
        with mock.patch.object(esquemas, 'aplicar_validadores', return_value={
            nombre: 'actualizado' for nombre in esquemas.COLECCIONES
        }), mock.patch('builtins.input') as preguntar:
            self._ejecutar('--si')
        preguntar.assert_not_called()
