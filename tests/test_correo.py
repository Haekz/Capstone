"""Correos de texto plano (alumnos.correo.enviar): el texto llega tal cual, sin escapar HTML.

render_to_string escapa siempre, aunque la plantilla sea .txt: "O'Higgins" llegaba como
"O&#x27;Higgins". Los correos usan su propio motor de plantillas sin autoescape; las paginas no.
"""

from django.core import mail
from django.template import engines
from django.test import SimpleTestCase

from alumnos.correo import enviar

NOMBRE = "Bernardo O'Higgins"
TEXTO = 'Clase "especial" de Física & Química <hoy>.'


class CorreoTextoPlanoTests(SimpleTestCase):

    def test_el_correo_llega_sin_entidades_html(self):
        self.assertTrue(enviar('Aviso', 'alumnos/correo_aviso_profesor.txt',
                               {'nombre': NOMBRE, 'texto': TEXTO}, 'profe@example.com'))
        cuerpo = mail.outbox[0].body
        self.assertIn(f'Hola {NOMBRE},', cuerpo)
        self.assertIn(TEXTO, cuerpo)
        self.assertNotIn('&#x27;', cuerpo)
        self.assertNotIn('&quot;', cuerpo)

    def test_las_paginas_html_siguen_escapando(self):
        """Resguardo contra XSS: el autoescape solo se apaga para los correos, nunca en el motor principal."""
        pagina = engines['django'].from_string('{{ valor }}').render({'valor': '<script>'})
        self.assertEqual(pagina, '&lt;script&gt;')
