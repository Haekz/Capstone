"""Los colores de estado en claro se leen en los 5 portales: --ok (verde) y --warn (ambar) dan 4,5:1 sobre blanco y en su
chip -soft sobre el fondo lila de la pagina (WCAG 1.4.3). Antes, #0f8a60 daba 3,55:1 y #b45309 4,2:1 en esos chips; medido
en el navegador el 21-nov (ok_medir_contraste.py, fuera del repo). Cada token esta repetido en cada portal y algunos usos
lo llevan fijo (fondos que no cambian con el tema): estas pruebas tambien impiden que las copias se separen.
"""

import re

from django.test import SimpleTestCase

from tests.test_planes_en_portal import _contraste, _leer

TOKENS = ('--ok', '--warn')
HOJAS = {  # portal: hoja que define los tokens (la primera definicion es la del tema claro)
    'alumno y apoderado': 'alumnos/static/alumnos/css/alumn_1/13_pulido.css',
    'docente': 'user_profesor/static/user_profesor/panel/06a_pulido_docente_marco.css',
    'admin': 'admin_portal/static/admin_portal/css/admin_panel/06a_pulido_admin_marco.css',
    'soporte': 'admin_portal/static/admin_portal/css/admin_panel/07a_pulido_soporte_marco.css',
}
COPIAS_FIJAS = [  # (token, hoja, regla) que llevan el color claro escrito: su fondo es claro tambien en oscuro, o tienen
    # su propia regla para el oscuro
    ('--ok', HOJAS['alumno y apoderado'], r'#portal-alumno \.tc-vence'),  # tarjeta de clases del banner, siempre blanca
    ('--warn', HOJAS['alumno y apoderado'], r'#portal-alumno \.tc-vence--pronto'),
    ('--warn', 'admin_portal/static/admin_portal/css/admin_panel/05_rediseno_contenido.css', r'body\.light-mode \.badge-pendiente'),
    ('--warn', 'alumnos/static/alumnos/css/reservas.css', r'\.horario__cupos--pocos'),
    ('--warn', 'lbwus/static/recuperar.css', r'\.auth-icon--warn'),
]
FONDO_PAGINA = '#f6f5fa'  # fondo de la pagina en claro, medido en el navegador


def _claro(css, variable):
    return re.search(rf'(?<![-\w]){variable}:\s*([^;]+);', css).group(1).strip()


def _sobre(rgba, fondo):
    """Color hexadecimal de ``rgba(r, g, b, a)`` pintado sobre ``fondo``."""
    *color, alfa = (float(v) for v in re.findall(r'[\d.]+', rgba))
    base = [int(fondo.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return '#' + ''.join(f'{round(c * alfa + b * (1 - alfa)):02x}' for c, b in zip(color, base))


class ContrasteDeLosColoresDeEstadoTests(SimpleTestCase):

    def test_se_leen_sobre_blanco_y_en_su_chip_en_cada_portal(self):
        for token in TOKENS:
            for portal, hoja in HOJAS.items():
                css = _leer(hoja)
                color, chip = _claro(css, token), _sobre(_claro(css, f'{token}-soft'), FONDO_PAGINA)
                with self.subTest(token=token, portal=portal):
                    self.assertGreaterEqual(_contraste(color, '#ffffff'), 4.5)
                    self.assertGreaterEqual(_contraste(color, chip), 4.5)

    def test_los_cinco_portales_usan_el_mismo_color(self):
        for token in TOKENS:
            with self.subTest(token=token):
                self.assertEqual(len({_claro(_leer(hoja), token) for hoja in HOJAS.values()}), 1)

    def test_las_copias_fijas_usan_ese_mismo_color(self):
        for token, hoja, regla in COPIAS_FIJAS:
            with self.subTest(regla=regla):
                cuerpo = re.search(rf'(?m)^{regla} \{{([^}}]*)\}}', _leer(hoja)).group(1)
                self.assertEqual(_claro(cuerpo, 'color'), _claro(_leer(HOJAS['alumno y apoderado']), token))
