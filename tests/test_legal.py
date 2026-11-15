"""B7 (15-nov): paginas de Terminos y Privacidad, pie de pagina con enlaces y datos reales, y "Proximamente" en las redes.

Los datos del responsable (nombre, RUT, domicilio, correos) salen de settings.LEGAL. Hoy son de EJEMPLO: la prueba de
`settings.LEGAL` comprueba que cambiarlos en un solo lugar cambia todas las paginas, para que el dia que existan los
reales no haya que buscarlos por el sitio.
"""

import pathlib

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from alumnos import paquetes
from alumnos.templatetags.dinero import clp
from apoderados.models import Documento
from mensajes.retencion import DIAS_SIN_ACTIVIDAD

CSS_DEL_PIE = pathlib.Path(settings.BASE_DIR) / 'alumnos/static/alumnos/css/styles/03_footer_y_paginas.css'
OTROS_DATOS = {
    'nombre': 'Educa Mas SpA', 'rut': '77.123.456-7', 'domicilio': 'Calle Nueva 456, Valparaiso',
    'telefono': '+56 9 8765 4321', 'correo_datos': 'datos@educamas.cl', 'correo_contacto': 'hola@educamas.cl',
}


class PaginasLegalesTests(TestCase):

    def test_las_dos_paginas_existen_en_su_direccion(self):
        for nombre, ruta in (('terminos', '/terminos/'), ('privacidad', '/privacidad/')):
            with self.subTest(pagina=nombre):
                self.assertEqual(reverse(nombre), ruta)
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTemplateUsed(respuesta, f'alumnos/{nombre}.html')

    def test_privacidad_no_tapa_la_eliminacion_de_cuenta(self):
        """/privacidad/ ya tenia subrutas (supresiones): la raiz nueva convive con ellas."""
        self.assertEqual(reverse('eliminar_cuenta'), '/privacidad/eliminar-cuenta/')

    def test_terminos_muestran_los_precios_del_codigo(self):
        respuesta = self.client.get(reverse('terminos'))
        for cotizacion in paquetes.cotizar():
            with self.subTest(plan=cotizacion.plan.nombre):
                self.assertContains(respuesta, clp(cotizacion.precio))
                self.assertContains(respuesta, f'{cotizacion.plan.vigencia_dias} días')
        for precio_viejo in ('$15.000', '$59.000', '$116.000'):  # los del .txt de la raiz, ya desactualizado
            self.assertNotContains(respuesta, precio_viejo)

    def test_privacidad_muestra_las_retenciones_del_codigo(self):
        respuesta = self.client.get(reverse('privacidad'))
        self.assertContains(respuesta, f'{Documento.VIGENCIA.days} días')
        self.assertContains(respuesta, f'{DIAS_SIN_ACTIVIDAD} días sin actividad')
        self.assertContains(respuesta, f'{settings.OBSERVACIONES_MESES} meses')


class DatosDelResponsableTests(TestCase):

    def paginas(self):
        return [self.client.get(reverse(nombre)) for nombre in ('terminos', 'privacidad', 'contactos', 'home')]

    def test_las_paginas_muestran_los_datos_de_settings(self):
        for respuesta in self.client.get(reverse('privacidad')), self.client.get(reverse('terminos')):
            for clave in ('nombre', 'rut', 'domicilio', 'correo_datos'):
                with self.subTest(clave=clave):
                    self.assertContains(respuesta, settings.LEGAL[clave])

    @override_settings(LEGAL=OTROS_DATOS)
    def test_cambiar_los_datos_en_un_solo_lugar_cambia_todas_las_paginas(self):
        terminos, privacidad, contactos, home = self.paginas()
        for respuesta in terminos, privacidad:
            for clave in ('nombre', 'rut', 'domicilio', 'correo_datos'):
                self.assertContains(respuesta, OTROS_DATOS[clave])
        for respuesta in contactos, home:  # Contacto y el pie
            for clave in ('domicilio', 'telefono', 'correo_contacto'):
                self.assertContains(respuesta, OTROS_DATOS[clave])
        self.assertContains(contactos, 'tel:+56987654321')  # el enlace de llamada, sin espacios

    def test_ya_no_hay_datos_de_plantilla_en_el_pie_ni_en_contacto(self):
        for respuesta in self.paginas():
            for relleno in ('Vernon Rockville', '123-456-7890', 'tel:1234567890'):
                with self.subTest(relleno=relleno):
                    self.assertNotContains(respuesta, relleno)


class PieDePaginaTests(TestCase):

    def test_privacidad_y_terminos_son_enlaces(self):
        home = self.client.get(reverse('home'))
        self.assertContains(home, f'<a href="{reverse("privacidad")}">Privacidad</a>', html=True)
        self.assertContains(home, f'<a href="{reverse("terminos")}">Términos</a>', html=True)
        self.assertNotContains(home, 'footer-static-link')  # los marcadores "proximamente" que reemplazan

    def test_las_redes_que_faltan_siguen_marcadas_como_proximamente(self):
        # Pie: Facebook y X. Contacto: Facebook, X y YouTube, mas las 2 del pie que tambien lleva = 5.
        for nombre, cantidad in (('home', 2), ('contactos', 5)):
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()
                self.assertEqual(html.count('social-placeholder'), cantidad)
                self.assertEqual(html.count('próximamente"'), cantidad)  # aria-label: tambien lo oyen los lectores

    def test_el_cursor_sobre_una_red_que_falta_muestra_proximamente(self):
        css = CSS_DEL_PIE.read_text(encoding='utf-8')
        regla = css.split('.social-placeholder:hover::after', 1)[1].split('}', 1)[0]
        self.assertIn("content: 'Próximamente'", regla)
        self.assertIn('pointer-events: none', regla)  # el globo no debe quitarle el cursor al icono
