"""Revision QA: acceso por rol en TODAS las rutas del proyecto (tests/rutas_qa.py).

Riesgo que cubre: una vista nueva sin decorador (regla 1) o con el decorador de
otro rol queda abierta. Las pruebas recorren cada ruta con GET y con POST sin
datos (los ids de relleno no existen) como anonimo y como cada rol, y exigen que:
- nadie reciba 200 fuera de la lista de lo que su rol puede ver;
- el anonimo que hace POST a una accion termine en el login, no en la accion;
- ninguna ruta termine en error 500.

"Ver" es 200, salvo los JSON con ``success: false`` (los decoradores *_json
responden asi a quien no tiene el rol). Si agregas una ruta publica o de un rol,
agregala a la lista que corresponde: la prueba falla hasta entonces a proposito.

Limite: con ids inexistentes, una vista con id que pierde su decorador puede
seguir dando 404 y pasar. El acceso a objetos ajenos (IDOR) lo prueban con
objetos reales test_qa_reservas, test_qa_apoderados y test_qa_pagos.
"""

import json

from allauth.socialaccount.models import SocialApp
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import TestCase

from alumnos.models import Genero, Tutor
from apoderados.models import Apoderado
from tests.bugs_qa import bug_qa
from tests.rutas_qa import rutas
from tests.test_apoderados import crear_agente, crear_apoderado, entrar
from tests.test_especialidad import crear_profesor
from tests.test_progreso_alumno import crear_alumno

PUBLICAS = {
    'home', 'contactos', 'nosotros', 'planes', 'servicios', 'opcion_user', 'regis_alum', 'alumnos_reg',
    'custom_login_alumno', 'sesiones_disponibles', 'home_adm', 'regis_prof', 'registro_apoderado',
    'adolescente_registro', 'login', 'password_reset', 'password_reset_done', 'password_reset_confirm',
    'password_reset_complete',
    # allauth: el registro propio de allauth esta cerrado (LbwusAccountAdapter.is_open_for_signup).
    'account_login', 'account_inactive', 'account_signup', 'account_email_verification_sent',
    'account_reset_password', 'account_reset_password_from_key_done', 'account_reset_password_done',
    'socialaccount_login_cancelled',
    # Con SOCIALACCOUNT_LOGIN_ON_GET = False, el GET solo muestra el boton que hace POST (S-20).
    'google_login',
}
# Cualquier cuenta con sesion.
COMUNES = {
    'mis_notificaciones', 'password_change', 'password_change_done',
    # allauth (ver BUG-QA-03 en EmailDeAllauthTests).
    'account_reauthenticate', 'account_email', 'account_change_password', 'socialaccount_connections',
}
PROPIAS = {
    'alumno': {'alumno_pag1', 'mis_tickets', 'nuevo_ticket', 'eliminar_cuenta'},
    'profesor': {'panel_profesor', 'resenas_profesor', 'mis_tickets', 'nuevo_ticket', 'eliminar_cuenta'},
    'admin': {'dashboard_admin', 'planes_adm', 'nosotros_adm', 'casos_escalados', 'crud', 'alumnos_Add',
              'regis_tutor', 'resenas_moderacion'},
    'soporte': {'titulos_adm', 'apoderados_revision', 'panel_soporte', 'mensajes_revision', 'requerimientos',
                'requerimiento_nuevo'},
    'apoderado': {'portal_apoderado', 'apoderado_registrar_estudiante', 'apoderado_vincular_estudiante',
                  'mensajes_apoderado', 'mis_tickets', 'nuevo_ticket', 'eliminar_cuenta'},
}


# Redirigen siempre, sin hacer nada (o inician Google): su destino no es el login.
SOLO_REDIRIGEN = {
    'puerta', 'alumnos_index', 'reporte_alumnos',  # a la portada o a crud, que exige admin
    'confirmacion',  # sin token_ws ni TBK_TOKEN vuelve a planes
    'google_login',  # POST: lleva a accounts.google.com (S-20)
    None,  # /accounts/social/signup/ -> /accounts/3rdparty/signup/ (ruta antigua de allauth, sin nombre)
}
CON_BUG_O_503 = {'alumnos_findEdit', 'alumnos_del', 'comunidad_salud'}
# Lo que responden al anonimo los endpoints JSON privados (decoradores *_json y las vistas que lo validan a mano).
RECHAZOS_DE_SESION = {
    'Sesión inválida.',
    'Debes iniciar sesión como alumno.',
    'No tienes permiso para crear administradores.',
}


def es_acceso(respuesta):
    if respuesta.status_code != 200:
        return False
    if respuesta.get('Content-Type', '').startswith('application/json'):
        return json.loads(respuesta.content).get('success') is not False
    return True


def es_salida(url, nombre):
    """El logout cierra la sesion: se prueba aparte."""
    return 'logout' in (nombre or '') or url.endswith(('/salir/', '/logout/'))


class Escenario(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Sin la app de Google, allauth lanza DoesNotExist en /accounts/google/login/ (en produccion existe).
        app = SocialApp.objects.create(provider='google', name='Google', client_id='qa', secret='qa')
        app.sites.add(Site.objects.get_current())
        genero = Genero.objects.create(descripcion='Otro')
        alumno = crear_alumno('11111111-1', 'Ana', genero)
        profesor = crear_profesor('33333333-3', 'profe@demo.cl', None)
        admin = Tutor.objects.create(user=get_user_model().objects.create_user(
            '10101010-1', rut='10101010-1', password='Clave-QA-2026', email='admin@demo.cl'))
        agente = crear_agente('20202020-2', lider=True)
        apoderado = crear_apoderado('12345678-5', Apoderado.VERIFICADO)
        cls.roles = {
            'alumno': (alumno.user, {'alumno_id': alumno.id_alumno}),
            'profesor': (profesor.user, {'profesor_id': profesor.id_profesor}),
            'admin': (admin.user, {'admin_id': admin.id_tutor}),
            'soporte': (agente.user, {'soporte_id': agente.id_agente}),
            'apoderado': (apoderado.user, {'apoderado_id': apoderado.id_apoderado}),
        }

    def como(self, rol):
        self.client.logout()
        if rol != 'anonimo':
            user, sesion = self.roles[rol]
            entrar(self.client, user, **sesion)

    def recorrer(self, rol, metodo='get'):
        """{(url, nombre): respuesta} de cada ruta como ``rol``; un error de la vista queda como 500."""
        self.como(rol)
        resultado = {}
        for url, nombre, _ in rutas():
            if es_salida(url, nombre):
                continue
            self.client.raise_request_exception = False  # un 500 es un dato, no corta el recorrido
            resultado[(url, nombre)] = getattr(self.client, metodo)(url)
            if rol != 'anonimo' and not self.client.session.get(next(iter(self.roles[rol][1]))):
                self.como(rol)  # alguna vista cerro la sesion: se vuelve a entrar
        return resultado


class AccesoPorRolTests(Escenario):

    def test_el_anonimo_solo_ve_las_paginas_publicas(self):
        vistas = {nombre for (url, nombre), r in self.recorrer('anonimo').items() if es_acceso(r)}
        self.assertEqual(vistas - PUBLICAS, set())

    def test_cada_rol_solo_ve_lo_publico_lo_comun_y_lo_propio(self):
        for rol, propias in PROPIAS.items():
            with self.subTest(rol=rol):
                vistas = {nombre for (url, nombre), r in self.recorrer(rol).items() if es_acceso(r)}
                self.assertEqual(vistas - PUBLICAS - COMUNES - propias, set())

    def test_las_paginas_propias_de_cada_rol_si_abren(self):
        """La otra mitad: la lista no esta inflada con paginas que el rol no ve."""
        for rol, propias in PROPIAS.items():
            with self.subTest(rol=rol):
                vistas = {nombre for (url, nombre), r in self.recorrer(rol).items() if es_acceso(r)}
                self.assertEqual(propias - vistas, set())

    def test_ninguna_ruta_da_error_500_con_ids_inexistentes(self):
        """Un id que no existe es 404, no 500. Ver aparte BUG-QA-04 (id no numerico en alumnos_findEdit
        y alumnos_del) y la salud de MongoDB (503 esperado)."""
        for rol in ('anonimo', *PROPIAS):
            for metodo in ('get', 'post'):
                with self.subTest(rol=rol, metodo=metodo):
                    errores = {nombre for (url, nombre), r in self.recorrer(rol, metodo).items()
                               if r.status_code >= 500 and nombre not in CON_BUG_O_503}
                    self.assertEqual(errores, set())

    def test_por_post_nadie_recibe_200_fuera_de_lo_suyo(self):
        """Riesgo: una accion con @require_POST pierde su decorador; por GET sigue dando 405 y no se nota."""
        for rol, propias in {'anonimo': set(), **PROPIAS}.items():
            with self.subTest(rol=rol):
                permitidas = PUBLICAS if rol == 'anonimo' else PUBLICAS | COMUNES | propias
                vistas = {nombre for (url, nombre), r in self.recorrer(rol, 'post').items() if es_acceso(r)}
                self.assertEqual(vistas - permitidas, set())

    def test_el_post_anonimo_a_una_accion_termina_en_el_login(self):
        """Si una accion redirige al anonimo a otro lugar que el login, probablemente se ejecuto."""
        fuera = {(url, nombre, r['Location']) for (url, nombre), r in self.recorrer('anonimo', 'post').items()
                 if r.status_code in (301, 302) and nombre not in SOLO_REDIRIGEN
                 and not r['Location'].startswith(('/accounts/login/', '/profesor/registro_profesor'))}
        self.assertEqual(fuera, set())

    def test_el_post_anonimo_a_un_json_privado_recibe_un_rechazo_de_sesion(self):
        """Con datos vacios, una accion sin decorador tambien responde success: false (por validacion):
        lo que la delata es el mensaje. El anonimo solo debe leer rechazos de sesion."""
        mensajes = {nombre: json.loads(r.content).get('message')
                    for (url, nombre), r in self.recorrer('anonimo', 'post').items()
                    if r.get('Content-Type', '').startswith('application/json') and nombre not in PUBLICAS}
        self.assertEqual({n: m for n, m in mensajes.items() if m not in RECHAZOS_DE_SESION}, {})

    def test_la_salud_de_mongodb_da_503_sin_mongodb_y_solo_al_admin(self):
        """503 es lo esperado sin MONGODB_URI (comunidad/views.py), no un error."""
        self.como('admin')
        self.assertEqual(self.client.get('/comunidad/salud/').status_code, 503)
        self.como('alumno')
        self.assertFalse(es_acceso(self.client.get('/comunidad/salud/')))


class IdNoNumericoTests(Escenario):

    @bug_qa('BUG-QA-04', 'alumnos_findEdit usa <str:pk> sobre un campo entero: un id no numerico da 500')
    def test_un_id_no_numerico_en_alumnos_findedit_es_404(self):
        self.como('admin')
        self.client.raise_request_exception = False
        self.assertEqual(self.client.get('/admin_portal/alumnos_findEdit/x/').status_code, 404)

    @bug_qa('BUG-QA-04', 'alumnos_del usa <str:pk> sobre un campo entero: un id no numerico da 500')
    def test_un_id_no_numerico_en_alumnos_del_es_404(self):
        self.como('admin')
        self.client.raise_request_exception = False
        self.assertEqual(self.client.post('/admin_portal/alumnos_del/x/').status_code, 404)


class EmailDeAllauthTests(Escenario):
    """Riesgo: cambiar el correo de la cuenta sin las validaciones del proyecto.

    El correo identifica la cuenta en el login (RutOrEmailBackend) y en Google
    (google_adapter.buscar_usuario_por_correo usa .first()): dos cuentas con el
    mismo correo mezclan identidades. El registro y el cambio de datos validan que
    el correo sea unico (alumnos/utils.py, user_profesor/cambio_cuenta.py), pero
    /accounts/email/ de allauth queda abierto a toda cuenta con sesion.
    """

    def setUp(self):
        self.ana = self.roles['alumno'][0]
        self.otro = self.roles['profesor'][0]
        self.como('alumno')

    def poner_como_principal(self, correo):
        self.client.post('/accounts/email/', {'action_add': '', 'email': correo})
        self.client.post('/accounts/email/', {'action_primary': '', 'email': correo})
        self.ana.refresh_from_db()

    @bug_qa('BUG-QA-03', '/accounts/email/ de allauth deja poner el correo de otra cuenta')
    def test_no_se_puede_tomar_el_correo_de_otra_cuenta(self):
        self.poner_como_principal(self.otro.email)
        self.assertNotEqual(self.ana.email.lower(), self.otro.email.lower())

    @bug_qa('BUG-QA-03', '/accounts/email/ de allauth cambia el correo sin confirmarlo')
    def test_el_correo_no_cambia_sin_confirmarlo(self):
        anterior = self.ana.email
        self.poner_como_principal('sin-confirmar@demo.cl')
        self.assertEqual(self.ana.email, anterior)
