"""Accesibilidad (WCAG 4.1.2): los botones de solo icono del portal del alumno tienen nombre."""

import re

from django.test import TestCase
from django.urls import reverse

from alumnos.models import Genero
from tests.test_especialidad import CLAVE
from tests.test_progreso_alumno import crear_alumno
from tests.test_suscripciones import dar_plan

RUT_ANA = '11111111-1'
BOTON_SOLO_ICONO = re.compile(r'<button\b[^>]*>\s*<i [^>]*></i>\s*</button>')


class BotonesConNombreTests(TestCase):

    def test_portal_sin_botones_de_solo_icono_anonimos(self):
        dar_plan(crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro')))
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        html = self.client.get(reverse('alumno_pag1')).content.decode()
        sin_nombre = [b for b in BOTON_SOLO_ICONO.findall(html)
                      if 'aria-label=' not in b and 'title=' not in b]
        self.assertEqual(sin_nombre, [])
