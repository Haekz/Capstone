"""Limpieza del 15-nov: lo guardado en el navegador va por cuenta (B6) y las paginas no afirman cifras sin respaldo.

B6: favoritos, intereses y bienvenida se guardaban con un nombre fijo en localStorage, asi que dos cuentas en un mismo
equipo se mezclaban. Ahora el nombre lleva el id de la cuenta (claveLocal en panel/js/datos.js).
"""

import pathlib
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tests.test_paquetes import RUT_ANA, RUT_BETO, Escenario

JS_DEL_PANEL = pathlib.Path(settings.BASE_DIR) / 'alumnos' / 'templates' / 'alumnos' / 'includes' / 'panel' / 'js'
CLAVES_DEL_NAVEGADOR = ('favorite-teachers', 'selected-topics', 'first_login_done')


class AlmacenamientoPorCuentaTests(Escenario):

    def id_de_cuenta_en_el_panel(self, rut):
        self.entrar(rut)
        html = self.client.get(reverse('alumno_pag1')).content.decode()
        encontrado = re.search(r'<script id="cuenta-id" type="application/json">([^<]*)</script>', html)
        self.assertIsNotNone(encontrado, 'el panel no entrega el id de la cuenta al JS')
        return encontrado.group(1)

    def test_el_panel_entrega_el_id_de_la_cuenta_que_entro(self):
        pk = get_user_model().objects.get(username=RUT_ANA).pk
        self.assertEqual(self.id_de_cuenta_en_el_panel(RUT_ANA), str(pk))

    def test_dos_cuentas_no_comparten_clave(self):
        self.assertNotEqual(self.id_de_cuenta_en_el_panel(RUT_ANA), self.id_de_cuenta_en_el_panel(RUT_BETO))

    def test_ninguna_clave_del_navegador_queda_suelta(self):
        """Toda lectura o escritura pasa por claveLocal(...): un nombre fijo volveria a mezclar cuentas."""
        for archivo in JS_DEL_PANEL.glob('*.js'):
            texto = archivo.read_text(encoding='utf-8')
            for clave in CLAVES_DEL_NAVEGADOR:
                with self.subTest(archivo=archivo.name, clave=clave):
                    self.assertNotRegex(texto, rf"localStorage\.(get|set)Item\(\s*['\"]{clave}['\"]")

    def test_las_tres_claves_se_siguen_usando_con_el_id(self):
        todo = ''.join(a.read_text(encoding='utf-8') for a in JS_DEL_PANEL.glob('*.js'))
        for clave in CLAVES_DEL_NAVEGADOR:
            with self.subTest(clave=clave):
                self.assertIn(f"claveLocal('{clave}')", todo)


class SinCifrasSinRespaldoTests(TestCase):
    """\"Mas de 10.000 profesionales\" no tiene respaldo: no debe volver a las paginas publicas."""

    def test_las_paginas_publicas_no_afirman_10_000(self):
        for nombre in ('home', 'nosotros', 'login'):
            with self.subTest(pagina=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 200)
                self.assertNotContains(respuesta, '10.000')
