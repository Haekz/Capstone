"""Portal del alumno: cada var(--x) que usa su pagina debe estar definida en lo que la pagina carga.

Una variable sin definir no da error: el borde queda invisible, el fondo transparente. Estaban rotas --border-color,
--bg-card, --text-dark y --border (copiadas del portal admin / de la sala virtual, donde si existen). En el portal
del alumno los tokens son --line (borde), --white (fondo de tarjeta) y --text.
"""

from django.test import SimpleTestCase

from .css_vars import sin_definir

# Lo unico que carga Alumno_pag1.html: la propia plantilla (estilos en linea) y sus dos hojas.
PAGINA_ALUMNO = [
    'alumnos/templates/alumnos/Alumno_pag1.html',
    'alumnos/static/alumnos/css/alumn_1.css',
    'alumnos/static/alumnos/css/avisos.css',
]


class VariablesCssDelPortalAlumnoTests(SimpleTestCase):

    def test_toda_variable_css_del_portal_alumno_esta_definida(self):
        self.assertEqual(sin_definir(PAGINA_ALUMNO, definidas_en=PAGINA_ALUMNO), {})
