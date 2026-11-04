"""SCRUM-93 (S4-13): almacenamiento privado y configuracion productiva.

Ver docs/CONFIGURACION_PRODUCCION.md. Los permisos de ``ver_titulo`` estan en
tests.test_google_y_titulo (test_archivo_del_titulo_solo_lo_ven_admins).
"""

import os
import re
import runpy
import tempfile
from pathlib import Path
from unittest import mock

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.checks import run_checks
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import storages
from django.db import models
from django.test import SimpleTestCase, TestCase, override_settings

from apoderados import documentos
from apoderados.models import Documento
from tests.test_menores_prerrequisitos import User
from alumnos.models import Tutor

SETTINGS = Path(settings.BASE_DIR) / 'lbwus' / 'settings.py'
VARIABLES_DE_ENTORNO = ('SECRET_KEY', 'DEBUG', 'DATABASE_URL')
URL_POSTGRES = 'postgresql://usuario:clave@localhost:5432/lbwus'


def cargar_settings(**entorno):
    """Ejecuta lbwus/settings.py en limpio con esas variables (sin tocar los settings activos).

    Trae una DATABASE_URL de PostgreSQL por defecto; ``DATABASE_URL=None`` la quita.
    """
    limpio = {k: v for k, v in os.environ.items() if k not in VARIABLES_DE_ENTORNO}
    pedido = {'DATABASE_URL': URL_POSTGRES, **entorno}
    with mock.patch.dict(os.environ, {**limpio, **{k: v for k, v in pedido.items() if v is not None}}, clear=True):
        return runpy.run_path(str(SETTINGS))


class BaseDeDatosTests(SimpleTestCase):
    """La base es siempre PostgreSQL: ya no hay SQLite de reserva."""

    def test_sin_database_url_no_arranca(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'DATABASE_URL'):
            cargar_settings(DATABASE_URL=None)

    def test_una_url_que_no_es_postgresql_no_arranca(self):
        for url in ('sqlite:///db.sqlite3', 'mysql://u:c@localhost/lbwus', ''):
            with self.subTest(url=url):
                with self.assertRaisesMessage(ImproperlyConfigured, 'PostgreSQL'):
                    cargar_settings(DATABASE_URL=url)

    def test_con_url_de_postgresql_la_usa(self):
        for url in (URL_POSTGRES, URL_POSTGRES.replace('postgresql://', 'postgres://')):
            with self.subTest(url=url):
                base = cargar_settings(DATABASE_URL=url)['DATABASES']['default']
                self.assertEqual(base['ENGINE'], 'django.db.backends.postgresql')
                self.assertEqual((base['HOST'], base['PORT'], base['NAME']), ('localhost', 5432, 'lbwus'))
                self.assertEqual(base['CONN_MAX_AGE'], 600)


class SecretKeyTests(SimpleTestCase):

    def test_produccion_sin_secret_key_no_arranca(self):
        with self.assertRaisesMessage(ImproperlyConfigured, 'SECRET_KEY'):
            cargar_settings(DEBUG='False')

    def test_produccion_con_secret_key_la_usa(self):
        ajustes = cargar_settings(DEBUG='False', SECRET_KEY='clave-de-prueba')
        self.assertEqual((ajustes['DEBUG'], ajustes['SECRET_KEY']), (False, 'clave-de-prueba'))

    def test_desarrollo_sin_secret_key_usa_la_insegura(self):
        ajustes = cargar_settings()
        self.assertTrue(ajustes['DEBUG'])
        self.assertTrue(ajustes['SECRET_KEY'].startswith('django-insecure-'))


class DocumentosClaveTests(SimpleTestCase):
    """Documentos de apoderados: cifrados con DOCUMENTOS_CLAVE, no con SECRET_KEY."""

    CLAVE = Fernet.generate_key().decode()

    def test_produccion_sin_documentos_clave_no_cifra(self):
        with override_settings(DEBUG=False, DOCUMENTOS_CLAVE=''):
            with self.assertRaisesMessage(ImproperlyConfigured, 'DOCUMENTOS_CLAVE'):
                documentos._cifrador()

    def test_desarrollo_sin_documentos_clave_usa_la_derivada(self):
        with override_settings(DEBUG=True, DOCUMENTOS_CLAVE=''):
            self.assertEqual(documentos.descifrar(documentos._cifrador().encrypt(b'carnet')), b'carnet')

    def test_con_documentos_clave_rotar_secret_key_no_pierde_documentos(self):
        with override_settings(DOCUMENTOS_CLAVE=self.CLAVE, SECRET_KEY='antes'):
            cifrado = documentos._cifrador().encrypt(b'carnet')
        with override_settings(DOCUMENTOS_CLAVE=self.CLAVE, SECRET_KEY='despues'):
            self.assertEqual(documentos.descifrar(cifrado), b'carnet')

    def test_lo_cifrado_con_la_derivada_se_lee_al_definir_documentos_clave(self):
        """Transicion: lo subido antes de definir la variable sigue leyendose."""
        with override_settings(DEBUG=True, DOCUMENTOS_CLAVE='', SECRET_KEY='actual'):
            cifrado = documentos._cifrador().encrypt(b'carnet')
        with override_settings(DOCUMENTOS_CLAVE=self.CLAVE, SECRET_KEY='actual'):
            self.assertEqual(documentos.descifrar(cifrado), b'carnet')

    def test_lo_cifrado_con_la_derivada_se_pierde_si_rota_secret_key(self):
        """Por esto DOCUMENTOS_CLAVE es obligatoria: SCRUM-81 roto SECRET_KEY."""
        with override_settings(DEBUG=True, DOCUMENTOS_CLAVE='', SECRET_KEY='antes'):
            cifrado = documentos._cifrador().encrypt(b'carnet')
        with override_settings(DOCUMENTOS_CLAVE=self.CLAVE, SECRET_KEY='despues'):
            with self.assertRaises(InvalidToken):
                documentos.descifrar(cifrado)

    def test_check_deploy_avisa_si_falta_o_no_es_valida(self):
        casos = {'': 'apoderados.E001', 'no-es-fernet': 'apoderados.E002', self.CLAVE: None}
        for clave, esperado in casos.items():
            with self.subTest(clave=clave), override_settings(DOCUMENTOS_CLAVE=clave):
                ids = {e.id for e in run_checks(include_deployment_checks=True) if e.id.startswith('apoderados.')}
                self.assertEqual(ids, {esperado} if esperado else set())


class ArchivosPrivadosTests(TestCase):
    """Nada de MEDIA_ROOT se publica en /media/: titulos y fotos solo por vistas con permiso."""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        for ruta in ('titulos/profesor_1.pdf', 'perfiles/foto.jpg'):
            archivo = Path(carpeta.name) / ruta
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_bytes(b'%PDF-1.4 privado')
        ajuste = override_settings(MEDIA_ROOT=carpeta.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    def test_media_no_se_sirve_ni_a_anonimos_ni_a_admins(self):
        admin = User.objects.create_user('10101010-1', password='x', rol='admin')
        tutor = Tutor.objects.create(user=admin)
        for nombre, preparar in (('anonimo', lambda: None), ('admin', lambda: self.entrar_admin(admin, tutor))):
            preparar()
            for url in ('/media/titulos/profesor_1.pdf', '/media/perfiles/foto.jpg'):
                with self.subTest(nombre, url=url):
                    self.assertEqual(self.client.get(url).status_code, 404)

    def entrar_admin(self, user, tutor):
        self.client.force_login(user)
        sesion = self.client.session
        sesion['admin_id'] = tutor.id_tutor
        sesion.save()

    def test_documentos_de_apoderados_viven_cifrados_en_la_base(self):
        """No van a disco (ni al volumen): BinaryField cifrado, sin FileField."""
        self.assertIsInstance(Documento._meta.get_field('contenido'), models.BinaryField)
        self.assertFalse([f for f in Documento._meta.get_fields() if isinstance(f, models.FileField)])


class EstaticosTests(SimpleTestCase):
    """Con DEBUG=False, el manifiesto de WhiteNoise da error 500 si una plantilla
    pide un estatico que no existe. Las pruebas no usan manifiesto (lbwus/test_runner.py),
    asi que aqui se corre collectstatic con el almacenamiento de produccion."""

    PATRON = re.compile(r"""{%\s*static\s+['"]([^'"]+)['"]""")

    def estaticos_de_las_plantillas(self):
        carpetas = [Path(settings.BASE_DIR) / 'templates'] + [
            p for p in Path(settings.BASE_DIR).glob('*/templates') if '.venv' not in p.parts]
        for plantilla in (a for c in carpetas for a in c.rglob('*.html')):
            for ruta in self.PATRON.findall(plantilla.read_text(encoding='utf-8', errors='ignore')):
                yield plantilla.relative_to(settings.BASE_DIR), ruta

    def test_collectstatic_de_produccion_y_todo_estatico_de_las_plantillas_existe(self):
        """collectstatic falla si un CSS apunta a un archivo que no existe; despues,
        cada {% static %} de las plantillas debe estar en el manifiesto."""
        produccion = cargar_settings(DEBUG='False', SECRET_KEY='x')['STORAGES']
        with tempfile.TemporaryDirectory() as carpeta, \
                override_settings(STATIC_ROOT=carpeta, STORAGES=produccion):
            call_command('collectstatic', interactive=False, verbosity=0)
            faltan = []
            for plantilla, ruta in self.estaticos_de_las_plantillas():
                try:
                    storages['staticfiles'].url(ruta)
                except ValueError:
                    faltan.append(f'{plantilla}: {ruta}')
        self.assertEqual(faltan, [])

    def test_las_pruebas_no_dependen_de_collectstatic(self):
        # Manifest* hereda de StaticFilesStorage: por eso type() y no isinstance().
        self.assertIs(type(storages['staticfiles']), StaticFilesStorage)

    def test_produccion_usa_el_manifiesto_comprimido(self):
        ajustes = cargar_settings(DEBUG='False', SECRET_KEY='x')
        self.assertEqual(ajustes['STORAGES']['staticfiles']['BACKEND'],
                         'whitenoise.storage.CompressedManifestStaticFilesStorage')


class ProcfileTests(SimpleTestCase):

    def test_el_despliegue_se_detiene_si_falta_una_clave(self):
        """check --deploy (apoderados.E001/E002) corre antes de gunicorn y despues de collectstatic."""
        pasos = (Path(settings.BASE_DIR) / 'Procfile').read_text().removeprefix('web:').split('&&')
        pasos = [p.strip() for p in pasos]
        self.assertEqual([p.split()[2] if p.startswith('python') else p.split()[0] for p in pasos],
                         ['migrate', 'collectstatic', 'check', 'gunicorn'])
        self.assertIn('--deploy', pasos[2])
