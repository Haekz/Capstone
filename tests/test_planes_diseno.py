"""Planes, diseno mas profesional (21-nov): desglose plegado, etiqueta sobre el borde, precio por clase con su linea, casilla de
Terminos con estilo propio, enlace al perfil sin partirse y el selector del apoderado en celular. Datos ficticios.

El texto y las cifras siguen en la pagina (test_paquetes, test_precios_planes): aqui se fija QUE lugar ocupa cada cosa.
"""

import pathlib
import re

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from alumnos import paquetes
from alumnos.models import Genero
from alumnos.templatetags.dinero import clp
from tests.test_paquetes import Escenario
from tests.test_planes_en_portal import HOJAS, _leer
from tests.test_progreso_alumno import crear_alumno

RUT_NUEVA = '66666666-6'


def tarjetas(html):
    return re.findall(r'<article class="plan-card.*?</article>', html, flags=re.S)


class TarjetasDePlanesTests(Escenario):

    def pagina(self):
        return self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor}).content.decode()

    def test_hay_tres_tarjetas(self):
        self.assertEqual(len(tarjetas(self.pagina())), len(paquetes.PLANES))

    def test_el_desglose_va_plegado_y_no_entre_los_beneficios(self):
        for tarjeta in tarjetas(self.pagina()):
            desglose = re.search(r'<details class="plan-desglose">(.*?)</details>', tarjeta, flags=re.S).group(1)
            beneficios = re.search(r'<ul class="plan-features-list">(.*?)</ul>', tarjeta, flags=re.S).group(1)
            with self.subTest(tarjeta=tarjeta[:90]):
                self.assertNotIn('<details class="plan-desglose" open', tarjeta)  # plegado al abrir la pagina
                self.assertIn('<summary>Ver desglose</summary>', desglose)
                for texto in ('comisión LBWUS de 15%', 'IVA incluido', 'El profesor recibe'):
                    self.assertIn(texto, desglose)
                    self.assertNotIn(texto, beneficios)  # no compite con el precio ni con los beneficios
                self.assertIn('Vigencia de', beneficios)

    def test_los_beneficios_llevan_todos_el_mismo_icono(self):
        iconos = re.findall(r'<i class="(bi [\w-]+) check-icon"', self.pagina())
        self.assertEqual(len(iconos), 2 + 3 + 3)  # Flexible 2 beneficios (sin ahorro), Progreso 3, Intensivo 3
        self.assertEqual(set(iconos), {'bi bi-check-lg'})

    def test_la_etiqueta_es_solo_del_plan_con_mejor_precio_por_clase(self):
        html = self.pagina()
        self.assertEqual(html.count('class="plan-badge"'), 1)
        self.assertIn('<div class="plan-badge">Mejor precio por clase</div>', tarjetas(html)[-1])
        self.assertNotIn('Mayor descuento', html)  # no decia que descuento ni sobre que: el dato real es el precio por clase

    def test_el_precio_por_clase_va_en_su_propia_linea_y_no_en_la_letra_chica(self):
        html = self.pagina()
        for tarjeta, cotizacion in zip(tarjetas(html), paquetes.cotizar()):
            chica = re.search(r'<p class="plan-billing-info">(.*?)</p>', tarjeta, flags=re.S).group(1)
            with self.subTest(plan=cotizacion.plan.nombre):
                self.assertIn(f'<p class="plan-por-clase">{clp(cotizacion.precio_por_clase)} por clase</p>', tarjeta)
                self.assertNotIn('por clase', chica)
                self.assertIn('Sin renovación obligatoria', chica)

    def test_ver_perfil_del_profesor_va_en_su_propio_enlace_solo_para_el_alumno(self):
        self.entrar(self.ana.user.username)
        html = self.pagina()
        enlace = reverse('perfil_profesor', args=[self.profe.id_profesor])
        self.assertRegex(html, rf'<a class="pl-ver-perfil" href="{enlace}"><i class="bi bi-person-circle" aria-hidden="true"></i> '
                               r'Ver perfil del profesor</a>')
        self.assertNotRegex(html, r'<p>Clase suelta[^<]*<a')  # antes iba dentro del parrafo y se partia en dos lineas
        self.client.logout()
        self.assertNotIn('pl-ver-perfil', self.pagina())

    def test_la_casilla_de_terminos_va_en_cada_tarjeta_antes_del_boton(self):
        crear_alumno(RUT_NUEVA, 'Cris', Genero.objects.first())  # no acepto aun: su casilla esta pendiente
        self.entrar(RUT_NUEVA)
        for tarjeta in tarjetas(self.pagina()):
            with self.subTest(tarjeta=tarjeta[:90]):
                self.assertEqual(tarjeta.count('<label class="pl-acepta">'), 1)
                self.assertLess(tarjeta.index('class="pl-acepta"'), tarjeta.index('class="plan-btn-action"'))


class CondicionesYExplicacionBajoLasTarjetasTests(Escenario):
    """Decidido por Fran (21-nov): las condiciones son un control con «?» bajo las tarjetas, no una caja grande; la explicacion
    (clases de 60 minutos, comision, Webpay) va debajo en los portales y no encima; la caja lila del apoderado se quita."""

    EXPLICACION = 'Compras un paquete de clases con el profesor que elijas'

    def pagina(self, **parametros):
        return self.client.get(reverse('planes'), parametros).content.decode()

    def test_las_condiciones_son_un_control_plegable_bajo_las_tarjetas_en_el_sitio_y_en_el_portal(self):
        for quien in (None, self.ana):
            with self.subTest(quien=quien):
                if quien:
                    self.entrar(quien.user.username)
                html = self.pagina(profesor=self.profe.id_profesor)
                self.assertEqual(html.count('<details class="pl-ayuda">'), 1)
                self.assertIn('<summary class="pl-ayuda-btn"><i class="bi bi-question-circle" aria-hidden="true"></i> Condiciones</summary>', html)
                self.assertGreater(html.index('class="pl-ayuda"'), html.rindex('</article>'))  # bajo las tarjetas
                dentro = html.split('<details class="pl-ayuda">', 1)[1].split('</details>', 1)[0]
                self.assertIn('id="pl-condiciones-titulo"', dentro)  # y la lista completa sigue ahi, no se perdio
                self.assertEqual(html.count('class="pl-condiciones"'), 1)  # ya no hay una caja suelta
                self.client.logout()

    def test_ningun_comentario_de_la_plantilla_sale_en_la_pagina(self):
        """Un {# #} de Django solo vale en UNA linea: partido en dos, el texto crudo salia sobre el control (visto en el navegador)."""
        for quien in (None, self.ana):
            with self.subTest(quien=quien):
                if quien:
                    self.entrar(quien.user.username)
                html = self.pagina(profesor=self.profe.id_profesor)
                self.assertNotIn('{#', html)
                self.assertNotIn('#}', html)
                self.client.logout()

    def test_el_script_abre_las_condiciones_con_el_mouse_y_se_cierran_con_esc(self):
        html = self.pagina()
        for pieza in ("querySelector('.pl-ayuda')", "'mouseenter'", "'mouseleave'", "e.key === 'Escape'"):
            self.assertIn(pieza, html)

    def test_en_el_portal_del_alumno_la_explicacion_va_debajo_de_las_tarjetas(self):
        self.entrar(self.ana.user.username)
        html = self.pagina(profesor=self.profe.id_profesor)
        cuerpo = html.split('</head>', 1)[1]
        self.assertEqual(cuerpo.count(self.EXPLICACION), 1)
        self.assertGreater(cuerpo.index(self.EXPLICACION), cuerpo.rindex('</article>'))
        self.assertIn('<div class="pl-pie-resumen">', cuerpo)
        self.assertNotIn('sv-intro', cuerpo)  # sin hero arriba

    def test_en_el_sitio_publico_la_explicacion_sigue_en_el_hero_de_arriba(self):
        cuerpo = self.pagina().split('</head>', 1)[1]
        self.assertEqual(cuerpo.count(self.EXPLICACION), 1)
        self.assertLess(cuerpo.index(self.EXPLICACION), cuerpo.index('<article'))
        self.assertNotIn('pl-pie-resumen', cuerpo)

    def test_el_alumno_conserva_su_encabezado_con_el_profesor_y_el_enlace_al_perfil(self):
        """Solo se quito la caja del apoderado (test_apoderados_compras): la del alumno lleva el enlace al perfil."""
        self.entrar(self.ana.user.username)
        html = self.pagina(profesor=self.profe.id_profesor)
        self.assertIn(f'Precios con {self.profe.nombre}', html)
        self.assertIn('pl-ver-perfil', html)


class CssDePlanesTests(SimpleTestCase):
    """Reglas que costaron un bug visto en el navegador: si alguien las cambia, que la prueba lo diga."""

    PLANES = _leer(HOJAS[0])
    APODERADO = _leer('apoderados/static/apoderados/16_portal_apoderado.css')

    def regla(self, css, selector):
        for selectores, cuerpo in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            if selector in [s.strip() for s in selectores.split(',')]:
                return cuerpo
        self.fail(f'no hay una regla con el selector {selector}')

    def test_la_etiqueta_cabalga_sobre_el_borde_y_no_empuja_el_titulo(self):
        """Con top: 20px y padding-right: 150px en el titulo, 'Plan Intensivo' se partia en dos lineas y el precio y el
        boton de esa tarjeta quedaban mas abajo que en las otras dos."""
        self.assertRegex(self.regla(self.PLANES, '.plan-badge'), r'top:\s*-\d+px')
        self.assertNotIn('padding-right: 150px', self.PLANES)

    def test_la_casilla_tiene_estilo_propio_en_todos_los_marcos(self):
        """Su estilo vivia en styles/10_legal.css, que solo carga el sitio publico: en los portales no tenia ninguno."""
        cuerpo = self.regla(self.PLANES, '.plan-card .pl-acepta')
        self.assertRegex(cuerpo, r'display:\s*flex')
        self.assertRegex(cuerpo, r'padding:\s*\d')

    def test_la_casilla_de_la_tarjeta_oscura_tiene_el_texto_claro(self):
        """El texto de la casilla es --text (oscuro): sobre la tarjeta destacada 'Acepto los' desaparecia."""
        self.assertRegex(self.regla(self.PLANES, '.plan-card.featured .pl-acepta'), r'color:\s*#ffffff')

    def test_el_tema_oscuro_del_portal_se_escribe_pegado_al_body(self):
        """En el portal del alumno el body ES #portal-alumno: 'body.dark-mode #portal-alumno X' (con espacio) no coincide
        nunca. Asi 'Ver perfil del profesor' daba 2,3:1 en oscuro."""
        self.assertNotIn('body.dark-mode #portal-alumno', self.PLANES)
        self.assertIn('body.dark-mode#portal-alumno .pl-ver-perfil', self.PLANES)

    def test_las_condiciones_salen_en_una_ventanita_alcanzable_con_el_mouse(self):
        """WCAG 1.4.13: lo que sale al pasar el mouse debe poder alcanzarse; sin el puente, al bajar el mouse se cerraba."""
        cuerpo = self.regla(self.PLANES, '.pl-ayuda .pl-condiciones')
        self.assertRegex(cuerpo, r'position:\s*absolute')
        self.assertRegex(self.regla(self.PLANES, '.pl-ayuda .pl-condiciones::before'), r'top:\s*-\d+px')

    def test_ya_no_quedan_estilos_de_la_caja_ni_del_encabezado_que_se_quitaron(self):
        self.assertNotIn('pl-intro--portal', self.PLANES)  # el hero compacto del portal
        for muerto in ('.pl-condiciones', '.planes-header {', '.planes-header p'):
            self.assertNotIn(f'apo-planes {muerto}', self.APODERADO)

    def test_el_selector_del_apoderado_no_crece_en_la_columna_del_celular(self):
        """planes.css apila la fila en pantallas chicas: el flex-basis de 260px del select pasaba a ser su alto."""
        media = re.search(r'@media \(max-width: 768px\) \{\s*#portal-alumno\.portal-apoderado \.apo-planes \.pl-selector select \{([^{}]*)\}',
                          self.APODERADO)
        self.assertIsNotNone(media, '16_portal_apoderado.css no corrige el select en pantallas chicas')
        self.assertRegex(media.group(1), r'flex:\s*0 0 auto')
