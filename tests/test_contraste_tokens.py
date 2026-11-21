"""Los colores de estado en claro se leen: --ok (verde), --warn (ambar) y --bad (rojo, solo soporte) dan 4,5:1 sobre blanco
y en su chip -soft sobre el fondo lila de la pagina (WCAG 1.4.3). Antes, en esos chips, #0f8a60 daba 3,55:1, #b45309 4,2:1
y #c2410c 3,8:1; medido en el navegador el 21-nov (ok_medir_contraste.py, fuera del repo). Cada token esta repetido en cada
portal y algunos usos lo llevan fijo (fondos que no cambian con el tema): estas pruebas tambien impiden que las copias se
separen.

En admin, docente y soporte, --text-muted (2,99:1 en claro y 4,30:1 en oscuro) queda solo para iconos decorativos: todo lo
que es texto, control o indicador de estado va con --text-secondary.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from tests.test_planes_en_portal import _contraste, _leer

HOJAS = {  # portal: hoja que define los tokens (la primera definicion es la del tema claro)
    'alumno y apoderado': 'alumnos/static/alumnos/css/alumn_1/13_pulido.css',
    'docente': 'user_profesor/static/user_profesor/panel/06a_pulido_docente_marco.css',
    'admin': 'admin_portal/static/admin_portal/css/admin_panel/06a_pulido_admin_marco.css',
    'soporte': 'admin_portal/static/admin_portal/css/admin_panel/07a_pulido_soporte_marco.css',
}
TOKENS = {'--ok': tuple(HOJAS), '--warn': tuple(HOJAS), '--bad': ('soporte',)}  # token: portales que lo definen
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
        for token, portales in TOKENS.items():
            for portal in portales:
                css = _leer(HOJAS[portal])
                color, chip = _claro(css, token), _sobre(_claro(css, f'{token}-soft'), FONDO_PAGINA)
                with self.subTest(token=token, portal=portal):
                    self.assertGreaterEqual(_contraste(color, '#ffffff'), 4.5)
                    self.assertGreaterEqual(_contraste(color, chip), 4.5)

    def test_los_portales_usan_el_mismo_color(self):
        for token, portales in TOKENS.items():
            with self.subTest(token=token):
                self.assertEqual(len({_claro(_leer(HOJAS[portal]), token) for portal in portales}), 1)

    def test_las_copias_fijas_usan_ese_mismo_color(self):
        for token, hoja, regla in COPIAS_FIJAS:
            with self.subTest(regla=regla):
                cuerpo = re.search(rf'(?m)^{regla} \{{([^}}]*)\}}', _leer(hoja)).group(1)
                self.assertEqual(_claro(cuerpo, 'color'), _claro(_leer(HOJAS['alumno y apoderado']), token))


MARCO_ADMIN = 'admin_portal/static/admin_portal/css/admin_panel/04_rediseno_marco.css'  # tokens de texto y fondo
FAMILIA_ADMIN = [('admin_portal/static/admin_portal/css/admin_panel', '*.css'), ('admin_portal/templates', '**/*.html'),
                 ('user_profesor/static/user_profesor/panel', '*.css')]  # lo que hereda base_admin
MUTED_DECORATIVOS = {'.search-bar i', '.search-modal-header i', 'bi-calendar-x'}  # iconos que no informan nada nuevo


def _usos_de_muted():
    """Regla (CSS) o clase del icono (plantilla) de cada var(--text-muted) de la familia admin."""
    usos = set()
    for carpeta, patron in FAMILIA_ADMIN:
        for ruta in Path(settings.BASE_DIR, carpeta).glob(patron):
            texto = _leer(ruta.relative_to(settings.BASE_DIR).as_posix())
            if ruta.suffix == '.css':
                usos |= {s.strip() for s, cuerpo in re.findall(r'([^{}]+)\{([^}]*)\}', texto) if 'var(--text-muted' in cuerpo}
            else:
                usos |= {(re.findall(r'bi-[\w-]+', linea) or [linea.strip()[:60]])[0]
                         for linea in texto.splitlines() if 'var(--text-muted' in linea}
    return usos


class TextoSecundarioEnLugarDeMutedTests(SimpleTestCase):

    def test_muted_queda_solo_en_iconos_decorativos(self):
        self.assertEqual(_usos_de_muted(), MUTED_DECORATIVOS)

    def test_el_texto_secundario_se_lee_en_claro_y_en_oscuro(self):
        css = _leer(MARCO_ADMIN)
        temas = {'oscuro': re.search(r':root \{([^}]*)\}', css).group(1),
                 'claro': re.search(r'body\.light-mode \{([^}]*)\}', css).group(1)}
        for tema, bloque in temas.items():
            for fondo in ('--bg-main', '--bg-card'):
                with self.subTest(tema=tema, fondo=fondo):
                    self.assertGreaterEqual(_contraste(_claro(bloque, '--text-secondary'), _claro(bloque, fondo)), 4.5)
