"""Portal del alumno: cada var(--x) que usa su pagina debe estar definida en lo que la pagina carga.

Una variable sin definir no da error: el borde queda invisible, el fondo transparente. Estaban rotas --border-color,
--bg-card, --text-dark y --border (copiadas del portal admin / de la sala virtual, donde si existen). En el portal
del alumno los tokens son --line (borde), --white (fondo de tarjeta) y --text.
"""

from django.test import SimpleTestCase

from .css_vars import sin_definir

# Lo que carga el portal del alumno: el marco (base_alumno), la pagina (estilos en linea) y sus dos hojas.
PAGINA_ALUMNO = [
    'alumnos/templates/alumnos/base_alumno.html',
    'alumnos/templates/alumnos/Alumno_pag1.html',
    'alumnos/static/alumnos/css/alumn_1.css',
    'alumnos/static/alumnos/css/avisos.css',
]


class VariablesCssDelPortalAlumnoTests(SimpleTestCase):

    def test_toda_variable_css_del_portal_alumno_esta_definida(self):
        self.assertEqual(sin_definir(PAGINA_ALUMNO, definidas_en=PAGINA_ALUMNO), {})

    def test_notificaciones_dentro_del_portal_alumno_tiene_todas_sus_variables(self):
        # lista.css se escribio para el sitio publico (--surface, header fijo): alumn_1.css hace el puente.
        notificaciones = [
            'notificaciones/static/notificaciones/lista.css',
            'notificaciones/static/notificaciones/campanita.css',
            'notificaciones/templates/notificaciones/lista.html',
        ]
        hojas = [a for a in notificaciones if a.endswith('.css')]
        self.assertEqual(sin_definir(notificaciones, definidas_en=PAGINA_ALUMNO + hojas), {})
