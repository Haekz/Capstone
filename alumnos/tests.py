"""Tests del menu global, navegacion, estaticos y control de acceso."""

import re
from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
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

        self.assertEqual(
            len(nombres),
            1,
            "name='home' esta registrado mas de una vez; el reverse() se "
            "vuelve ambiguo y gana el ultimo urlconf cargado.",
        )


class MenuEstadoSesionTests(TestCase):
    """El menu global debe reflejar el estado real de la sesion."""

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Femenino')

        cls.user_alumno = User.objects.create_user(
            username='11111111-1', password='clave12345', first_name='Ana'
        )
        cls.alumno = Alumno.objects.create(
            user=cls.user_alumno,
            nombre='Ana Soto',
            rut='11111111-1',
            nivel_educacion='media',
            direccion='Calle 1',
            fecha_nacimiento=date(1995, 5, 20),
            correo_electronico='ana@lbwus.cl',
            genero=cls.genero,
        )

        cls.user_profesor = User.objects.create_user(
            username='22222222-2', password='clave12345', first_name='Beto'
        )
        cls.profesor = Profesor.objects.create(
            user=cls.user_profesor,
            nombre='Beto Rojas',
            rut='22222222-2',
            especialidad='Matematicas',
            direccion='Calle 2',
            fecha_nacimiento=date(1985, 3, 10),
            correo_electronico='beto@lbwus.cl',
            telefono='987654321',
            genero=cls.genero,
        )

        cls.user_tutor = User.objects.create_user(
            username='33333333-3', password='clave12345', first_name='Caro'
        )
        cls.tutor = Tutor.objects.create(
            user=cls.user_tutor,
            nombre='Caro Diaz',
            rut='33333333-3',
            direccion='Calle 3',
            fecha_nacimiento=date(1980, 1, 15),
            correo_electronico='caro@lbwus.cl',
            genero=cls.genero,
        )

    def _menu(self):
        """Renderiza el home y devuelve (html, contexto de sesion)."""
        respuesta = self.client.get(reverse('home'))

        self.assertEqual(respuesta.status_code, 200)

        return respuesta.content.decode(), respuesta.context['usuario_sesion']

    # -- visitante anonimo ------------------------------------------------

    def test_anonimo_ve_iniciar_y_registrarse(self):
        html, sesion = self._menu()

        self.assertFalse(sesion['autenticado'])
        self.assertIn(reverse('opcion_user'), html)
        self.assertNotIn('Cerrar sesion', html)
        self.assertNotIn('Cerrar sesi\u00f3n', html)

    # -- sesiones por rol -------------------------------------------------

    def test_alumno_ve_su_nombre_y_su_portal(self):
        self.client.force_login(self.user_alumno)

        html, sesion = self._menu()

        self.assertTrue(sesion['autenticado'])
        self.assertEqual(sesion['rol'], 'Alumno')
        self.assertEqual(sesion['url_panel'], reverse('alumno_pag1'))
        self.assertEqual(sesion['url_logout'], reverse('logout_alumno'))
        self.assertIn('Ana Soto', html)

    def test_profesor_ve_su_panel(self):
        self.client.force_login(self.user_profesor)

        _, sesion = self._menu()

        self.assertEqual(sesion['rol'], 'Profesor')
        self.assertEqual(sesion['url_panel'], reverse('panel_profesor'))
        self.assertEqual(sesion['url_logout'], reverse('logout_prof'))

    def test_tutor_ve_el_panel_admin(self):
        self.client.force_login(self.user_tutor)

        _, sesion = self._menu()

        self.assertEqual(sesion['rol'], 'Administrador')
        self.assertEqual(sesion['url_panel'], reverse('dashboard_admin'))
        self.assertEqual(sesion['url_logout'], reverse('logout_admin'))

    def test_staff_sin_perfil_tratado_como_admin(self):
        """login_admin() acepta staff sin Tutor asociado; el menu tambien."""
        staff = User.objects.create_user(
            username='staff', password='clave12345', is_staff=True
        )
        self.client.force_login(staff)

        _, sesion = self._menu()

        self.assertEqual(sesion['rol'], 'Administrador')

    def test_usuario_sin_perfil_puede_cerrar_sesion(self):
        """Sin perfil no hay panel, pero si debe poder salir."""
        huerfano = User.objects.create_user(
            username='huerfano', password='clave12345'
        )
        self.client.force_login(huerfano)

        _, sesion = self._menu()

        self.assertTrue(sesion['autenticado'])
        self.assertEqual(sesion['url_panel'], '')
        self.assertTrue(sesion['url_logout'])

    # -- el menu es global ------------------------------------------------

    def test_estado_visible_en_todas_las_paginas_del_menu(self):
        """El menu se hereda: debe reconocer la sesion en cualquier pagina."""
        self.client.force_login(self.user_alumno)

        for nombre in ('home', 'nosotros', 'servicios', 'planes', 'contactos'):
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre))

                self.assertTrue(
                    respuesta.context['usuario_sesion']['autenticado']
                )

    def test_logout_devuelve_el_menu_a_anonimo(self):
        """Cerrar sesion debe revertir el menu, no dejarlo pegado."""
        self.client.force_login(self.user_alumno)
        self.client.get(reverse('logout_alumno'))

        _, sesion = self._menu()

        self.assertFalse(sesion['autenticado'])


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
        cls.user = User.objects.create_user(
            username='44444444-4', password='clave12345', first_name='Dani'
        )
        cls.alumno = Alumno.objects.create(
            user=cls.user,
            nombre='Dani Luna',
            rut='44444444-4',
            nivel_educacion='superior',
            direccion='Calle 4',
            fecha_nacimiento=date(1998, 7, 2),
            correo_electronico='dani@lbwus.cl',
            genero=genero,
        )

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

        self.assertEqual(
            respuesta.status_code,
            200,
            'El portal del alumno no se renderizo.',
        )

        return respuesta.content.decode()

    def test_logo_del_portal_apunta_al_propio_portal(self):
        html = self._entrar_al_portal()

        enlace_logo = re.search(r'<a href="([^"]+)" class="logo">', html)

        self.assertIsNotNone(enlace_logo, 'No se encontro el enlace del logo.')
        self.assertEqual(enlace_logo.group(1), reverse('alumno_pag1'))

    def test_logo_del_portal_no_lleva_al_home_publico(self):
        """Blinda contra volver a apuntar el logo al sitio publico."""
        html = self._entrar_al_portal()

        enlace_logo = re.search(r'<a href="([^"]+)" class="logo">', html)

        self.assertNotEqual(enlace_logo.group(1), reverse('home'))

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

        menu.html tenia <i the="fab fa-twitter">: el autor escribio 'the='
        en vez de 'class='. El navegador ignora el atributo desconocido y
        no pinta nada. Como ese template no lo renderiza ninguna vista, se
        revisa el archivo directamente.
        """
        plantillas = Path(settings.BASE_DIR).glob('**/templates/**/*.html')

        # Atributos validos en un <i>; cualquier otro suele ser una errata.
        permitidos = re.compile(
            r'^(class|id|style|title|aria-[\w-]+|data-[\w-]+|role)$'
        )
        etiqueta_i = re.compile(r'<i\s+([a-zA-Z-]+)=')

        sospechosos = []
        for plantilla in plantillas:
            contenido = plantilla.read_text(encoding='utf-8', errors='ignore')

            for numero, linea in enumerate(contenido.splitlines(), start=1):
                for atributo in etiqueta_i.findall(linea):
                    if not permitidos.match(atributo):
                        sospechosos.append(
                            f'{plantilla.name}:{numero} -> <i {atributo}=...>'
                        )

        self.assertEqual(
            sospechosos,
            [],
            'Iconos con atributo mal escrito: ' + '; '.join(sospechosos),
        )

    def test_ningun_template_renderiza_href_vacio(self):
        """Barre las paginas publicas buscando marcadores sin sustituir."""
        for nombre in (
            'home', 'nosotros', 'servicios', 'planes',
            'contactos', 'simulador', 'opcion_user',
        ):
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()

                self.assertNotIn('href="{}"', html)


class CacheDespuesDelLogoutTests(TestCase):
    """Las paginas privadas no deben quedar en el cache del navegador.

    Sin 'no-store', el boton Atras vuelve a pintar el panel con los datos
    del usuario anterior aunque la sesion ya este cerrada: el navegador ni
    siquiera consulta al servidor. Se verifico que las respuestas salian
    sin ninguna cabecera de cache.
    """

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Femenino')

        cls.user_alumno = User.objects.create_user(
            username='66666666-6', password='clave12345', first_name='Eva'
        )
        cls.alumno = Alumno.objects.create(
            user=cls.user_alumno,
            nombre='Eva Mora',
            rut='66666666-6',
            nivel_educacion='media',
            direccion='Calle 6',
            fecha_nacimiento=date(1996, 4, 4),
            correo_electronico='eva@lbwus.cl',
            genero=cls.genero,
        )

        cls.user_profesor = User.objects.create_user(
            username='77777777-7', password='clave12345', first_name='Fito'
        )
        cls.profesor = Profesor.objects.create(
            user=cls.user_profesor,
            nombre='Fito Paez',
            rut='77777777-7',
            especialidad='Musica',
            direccion='Calle 7',
            fecha_nacimiento=date(1975, 3, 13),
            correo_electronico='fito@lbwus.cl',
            telefono='912345678',
            genero=cls.genero,
        )

        cls.user_tutor = User.objects.create_user(
            username='88888888-8', password='clave12345', first_name='Gabi'
        )
        cls.tutor = Tutor.objects.create(
            user=cls.user_tutor,
            nombre='Gabi Soto',
            rut='88888888-8',
            direccion='Calle 8',
            fecha_nacimiento=date(1982, 9, 9),
            correo_electronico='gabi@lbwus.cl',
            genero=cls.genero,
        )

    def _abrir(self, user, clave_sesion, valor, ruta):
        self.client.force_login(user)

        sesion = self.client.session
        sesion[clave_sesion] = valor
        sesion.save()

        return self.client.get(reverse(ruta))

    def _assert_sin_cache(self, respuesta):
        cache_control = respuesta.headers.get('Cache-Control', '')

        self.assertIn(
            'no-store',
            cache_control,
            'Sin no-store el boton Atras puede mostrar datos privados '
            'despues de cerrar sesion.',
        )

    def test_portal_alumno_no_se_cachea(self):
        respuesta = self._abrir(
            self.user_alumno, 'alumno_id', self.alumno.id_alumno, 'alumno_pag1'
        )

        self.assertEqual(respuesta.status_code, 200)
        self._assert_sin_cache(respuesta)

    def test_panel_profesor_no_se_cachea(self):
        respuesta = self._abrir(
            self.user_profesor, 'profesor_id', self.profesor.id_profesor,
            'panel_profesor',
        )

        self.assertEqual(respuesta.status_code, 200)
        self._assert_sin_cache(respuesta)

    def test_dashboard_admin_no_se_cachea(self):
        respuesta = self._abrir(
            self.user_tutor, 'admin_id', self.tutor.id_tutor, 'dashboard_admin'
        )

        self.assertEqual(respuesta.status_code, 200)
        self._assert_sin_cache(respuesta)

    def test_tras_logout_el_portal_exige_login(self):
        """El servidor debe negar el acceso, no solo ocultar el enlace."""
        self._abrir(
            self.user_alumno, 'alumno_id', self.alumno.id_alumno, 'alumno_pag1'
        )
        self.client.get(reverse('logout_alumno'))

        respuesta = self.client.get(reverse('alumno_pag1'))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse('login'), respuesta['Location'])


class ArchivosEstaticosTests(TestCase):
    """Todo {% static %} debe resolver a un archivo real.

    Habia 7 referencias rotas: un bootstrap.min.css/js local que nunca
    existio y rutas a las que les faltaba el prefijo de la app
    ('img/Logo.png' en vez de 'alumnos/img/Logo.png').
    """

    ETIQUETA_STATIC = re.compile(r'{%\s*static\s+[\'"]([^\'"]+)[\'"]')

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

        self.assertEqual(
            rotos,
            [],
            'Referencias a estaticos inexistentes: ' + '; '.join(rotos),
        )

    def test_sin_rutas_static_escritas_a_mano(self):
        """Un /static/... literal se rompe si cambia STATIC_URL."""
        literales = re.compile(r'(?:href|src)="(/static/[^"]+)"')
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
        cls.user = User.objects.create_user(
            username='99999999-9', password='clave12345', first_name='Hugo'
        )
        cls.tutor = Tutor.objects.create(
            user=cls.user,
            nombre='Hugo Vera',
            rut='99999999-9',
            direccion='Calle 9',
            fecha_nacimiento=date(1979, 6, 6),
            correo_electronico='hugo@lbwus.cl',
            genero=genero,
        )

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


class RegistroAdminTests(TestCase):
    """Crear administradores no puede ser un autoservicio publico.

    regis_tutor() era accesible sin sesion y ademas marcaba is_staff=True,
    asi que cualquiera con el formulario obtenia el portal admin Y el
    /admin/ de Django. Se verifico explotandolo antes de corregirlo.
    """

    RUT_NUEVO = '15133974-3'  # digito verificador valido (modulo 11)

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')

        cls.admin_user = User.objects.create_user(
            username='10101010-1', password='clave12345', first_name='Ada'
        )
        cls.admin_tutor = Tutor.objects.create(
            user=cls.admin_user,
            nombre='Ada Lopez',
            rut='10101010-1',
            direccion='Calle 10',
            fecha_nacimiento=date(1977, 2, 2),
            correo_electronico='ada@lbwus.cl',
            genero=cls.genero,
        )

    def _datos(self):
        return {
            'nombre': 'Intruso Anonimo',
            'rut': self.RUT_NUEVO,
            'direccion': 'Calle Falsa 123',
            'fecha_nacimiento': '1990-01-01',
            'correo_electronico': 'intruso@ejemplo.com',
            'telefono': '900000000',
            'genero': self.genero.id_genero,
            'password': 'clave12345',
            'confirm_password': 'clave12345',
        }

    def _entrar_como_admin(self):
        self.client.force_login(self.admin_user)

        sesion = self.client.session
        sesion['admin_id'] = self.admin_tutor.id_tutor
        sesion.save()

    # -- el registro publico esta cerrado ---------------------------------

    def test_anonimo_no_ve_el_formulario(self):
        respuesta = self.client.get(reverse('regis_tutor'))

        self.assertEqual(respuesta.status_code, 302)

    def test_anonimo_no_puede_crear_admins(self):
        respuesta = self.client.post(reverse('regis_tutor'), self._datos())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(
            User.objects.filter(username=self.RUT_NUEVO).exists(),
            'Un anonimo logro crear una cuenta de administrador.',
        )

    def test_un_alumno_tampoco_puede_crear_admins(self):
        """Estar autenticado no basta: hace falta ser administrador."""
        user = User.objects.create_user(username='12121212-1', password='x')
        Alumno.objects.create(
            user=user,
            nombre='Ines Paz',
            rut='12121212-1',
            nivel_educacion='media',
            direccion='Calle 12',
            fecha_nacimiento=date(1999, 8, 8),
            correo_electronico='ines@lbwus.cl',
            genero=self.genero,
        )
        self.client.force_login(user)

        respuesta = self.client.post(reverse('regis_tutor'), self._datos())

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(User.objects.filter(username=self.RUT_NUEVO).exists())

    def test_la_home_no_ofrece_registro_de_admin(self):
        """El boton publico 'Registrarme como Admin' ya no debe existir."""
        html = self.client.get(reverse('opcion_user')).content.decode()

        self.assertNotIn(reverse('regis_tutor'), html)

    # -- un admin si puede, pero sin repartir is_staff ---------------------

    def test_admin_si_puede_crear_otro_admin(self):
        self._entrar_como_admin()

        respuesta = self.client.post(reverse('regis_tutor'), self._datos())

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['success'])
        self.assertTrue(User.objects.filter(username=self.RUT_NUEVO).exists())

    def test_el_admin_creado_no_recibe_is_staff(self):
        """is_staff abre /admin/ de Django: se concede a mano, no por web."""
        self._entrar_como_admin()
        self.client.post(reverse('regis_tutor'), self._datos())

        nuevo = User.objects.get(username=self.RUT_NUEVO)

        self.assertFalse(nuevo.is_staff, 'No debe recibir acceso a /admin/.')
        self.assertFalse(nuevo.is_superuser)

    def test_el_admin_creado_si_entra_al_portal(self):
        """Quitar is_staff no debe dejarlo sin su panel."""
        self._entrar_como_admin()
        self.client.post(reverse('regis_tutor'), self._datos())

        self.client.get(reverse('logout_admin'))

        entrada = self.client.post(
            reverse('login_admin'),
            {'identificador': self.RUT_NUEVO, 'password': 'clave12345'},
        )

        self.assertTrue(entrada.json()['success'])
