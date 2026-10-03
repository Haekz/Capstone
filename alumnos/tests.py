"""Tests del menu global, navegacion, estaticos y control de acceso."""
import re
from datetime import date
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import get_resolver, reverse
from .models import Alumno, Genero, Profesor, Tutor

class HomeCanonicoTests(TestCase):
    """El home debe ser uno solo, y debe vivir en la raiz.

    Contexto: 'home' llego a estar registrado dos veces (en lbwus/urls.py y
    en alumnos/urls.py). Django permite nombres duplicados sin emitir ningun
    aviso: simplemente gana el ultimo registrado, asi que reverse('home')
    devolvia '/alumnos/' en vez de '/'.
    """

    def test_reverse_home_apunta_a_la_raiz(self):
        self.assertEqual(reverse('home'), '/')

    def test_home_responde_ok(self):
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_alumnos_index_redirige_al_home(self):
        """La URL antigua /alumnos/ no debe servir una copia del home."""
        respuesta = self.client.get('/alumnos/')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'], '/')

    def test_home_registrado_una_sola_vez(self):
        """Blinda contra volver a declarar name='home' en otra app."""
        nombres = get_resolver().reverse_dict.getlist('home')
        self.assertEqual(len(nombres), 1, "name='home' esta registrado mas de una vez; el reverse() se vuelve ambiguo y gana el ultimo urlconf cargado.")

class LogoNavegacionTests(TestCase):
    """El logo no debe sacar al usuario de su portal.

    El portal del alumno (Alumno_pag1.html) no hereda de base.html: tiene su
    propia barra. Su logo apuntaba al home publico, asi que un clic te sacaba
    del panel y te dejaba en la pagina de marketing. La sesion seguia viva,
    pero parecia un cierre de sesion.
    """

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Femenino')
        cls.user = User.objects.create_user(username='44444444-4', password='clave12345', first_name='Dani')
        cls.alumno = Alumno.objects.create(user=cls.user, nivel_educacion='superior')

    def _entrar_al_portal(self):
        """Inicia sesion como alumno y devuelve el HTML de su portal.

        La vista alumno_pag1() exige 'alumno_id' en la sesion, que es lo que
        hace custom_login(). force_login() por si solo no lo pone, y hay que
        guardar la sesion explicitamente para que persista entre requests.
        """
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['alumno_id'] = self.alumno.id_alumno
        sesion.save()
        respuesta = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(respuesta.status_code, 200, 'El portal del alumno no se renderizo.')
        return respuesta.content.decode()

    def _href_del_logo(self):
        """Devuelve el destino del logo del portal.

        Desde el rediseño el logo vive en el menu lateral con la clase
        'sb-brand' (antes era 'logo' en la barra superior).
        """
        html = self._entrar_al_portal()
        enlace_logo = re.search('<a href="([^"]+)" class="sb-brand">', html)
        self.assertIsNotNone(enlace_logo, 'No se encontro el enlace del logo.')
        return enlace_logo.group(1)

    def test_logo_del_portal_apunta_al_propio_portal(self):
        self.assertEqual(self._href_del_logo(), reverse('alumno_pag1'))

    def test_logo_del_portal_no_lleva_al_home_publico(self):
        """Blinda contra volver a apuntar el logo al sitio publico."""
        self.assertNotEqual(self._href_del_logo(), reverse('home'))

    def test_el_portal_sigue_ofreciendo_cerrar_sesion(self):
        """Quitar la salida por el logo no debe dejar al usuario encerrado."""
        html = self._entrar_al_portal()
        self.assertIn(reverse('logout_alumno'), html)

class EnlacesTemplatesTests(TestCase):
    """Los templates no deben servir enlaces rotos.

    simulador.html no hereda de base.html: tiene su propia barra, y sus
    botones traian href="{}" literal (restos de un .format() de Python).
    Un clic ahi recargaba la misma pagina.
    """

    def test_simulador_no_tiene_href_vacio(self):
        html = self.client.get(reverse('simulador')).content.decode()
        self.assertNotIn('href="{}"', html)

    def test_simulador_enlaza_login_y_registro(self):
        html = self.client.get(reverse('simulador')).content.decode()
        self.assertIn(reverse('login'), html)
        self.assertIn(reverse('opcion_user'), html)

    def test_los_iconos_declaran_class(self):
        """Un <i> con el atributo mal tecleado es un icono invisible.

        Un template antiguo tenia <i the="fab fa-twitter">: el autor escribio
        'the=' en vez de 'class='. El navegador ignora el atributo
        desconocido y no pinta nada. Se revisan los archivos directamente
        para cubrir tambien templates que ninguna vista renderiza.
        """
        plantillas = Path(settings.BASE_DIR).glob('**/templates/**/*.html')
        permitidos = re.compile('^(class|id|style|title|aria-[\\w-]+|data-[\\w-]+|role)$')
        etiqueta_i = re.compile('<i\\s+([a-zA-Z-]+)=')
        sospechosos = []
        for plantilla in plantillas:
            contenido = plantilla.read_text(encoding='utf-8', errors='ignore')
            for numero, linea in enumerate(contenido.splitlines(), start=1):
                for atributo in etiqueta_i.findall(linea):
                    if not permitidos.match(atributo):
                        sospechosos.append(f'{plantilla.name}:{numero} -> <i {atributo}=...>')
        self.assertEqual(sospechosos, [], 'Iconos con atributo mal escrito: ' + '; '.join(sospechosos))

    def test_ningun_template_renderiza_href_vacio(self):
        """Barre las paginas publicas buscando marcadores sin sustituir."""
        for nombre in ('home', 'nosotros', 'servicios', 'planes', 'contactos', 'simulador', 'opcion_user'):
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()
                self.assertNotIn('href="{}"', html)

class ArchivosEstaticosTests(TestCase):
    """Todo {% static %} debe resolver a un archivo real.

    Habia 7 referencias rotas: un bootstrap.min.css/js local que nunca
    existio y rutas a las que les faltaba el prefijo de la app
    ('img/Logo.png' en vez de 'alumnos/img/Logo.png').
    """
    ETIQUETA_STATIC = re.compile('{%\\s*static\\s+[\\\'"]([^\\\'"]+)[\\\'"]')

    def _plantillas(self):
        for plantilla in Path(settings.BASE_DIR).glob('**/templates/**/*.html'):
            if '.venv' not in str(plantilla):
                yield plantilla

    def test_todos_los_static_existen(self):
        rotos = []
        for plantilla in self._plantillas():
            contenido = plantilla.read_text(encoding='utf-8', errors='ignore')
            for numero, linea in enumerate(contenido.splitlines(), start=1):
                for ruta in self.ETIQUETA_STATIC.findall(linea):
                    if finders.find(ruta) is None:
                        rotos.append(f'{plantilla.name}:{numero} -> {ruta}')
        self.assertEqual(rotos, [], 'Referencias a estaticos inexistentes: ' + '; '.join(rotos))

    def test_sin_rutas_static_escritas_a_mano(self):
        """Un /static/... literal se rompe si cambia STATIC_URL."""
        literales = re.compile('(?:href|src)="(/static/[^"]+)"')
        encontrados = []
        for plantilla in self._plantillas():
            contenido = plantilla.read_text(encoding='utf-8', errors='ignore')
            for numero, linea in enumerate(contenido.splitlines(), start=1):
                for ruta in literales.findall(linea):
                    encontrados.append(f'{plantilla.name}:{numero} -> {ruta}')
        self.assertEqual(encontrados, [], '; '.join(encontrados))

class ReporteAlumnosTests(TestCase):
    """La ruta antigua del listado reventaba con HTTP 500.

    Apuntaba a 'alumnos/reporte_alumnos.html', un template inexistente, y
    ademas no validaba la sesion de administrador.
    """

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Femenino')
        cls.user = User.objects.create_user(username='99999999-9', password='clave12345', first_name='Hugo')
        cls.tutor = Tutor.objects.create(user=cls.user)

    def test_anonimo_no_recibe_error_500(self):
        respuesta = self.client.get(reverse('reporte_alumnos'))
        self.assertEqual(respuesta.status_code, 302)

    def test_anonimo_termina_en_el_login(self):
        """Siguiendo la redireccion no debe filtrarse el listado."""
        respuesta = self.client.get(reverse('reporte_alumnos'), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(reverse('login'), respuesta.redirect_chain[-1][0])

    def test_admin_ve_el_listado(self):
        self.client.force_login(self.user)
        sesion = self.client.session
        sesion['admin_id'] = self.tutor.id_tutor
        sesion.save()
        respuesta = self.client.get(reverse('reporte_alumnos'), follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(reverse('crud'), respuesta.redirect_chain[-1][0])