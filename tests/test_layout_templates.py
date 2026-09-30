"""El layout comun debe salir una sola vez y en todas las paginas publicas.

Navbar y footer viven en alumnos/templates/alumnos/includes/. Estos tests
detectan tanto una copia pegada a mano como un include roto.
"""

from django.test import TestCase
from django.urls import reverse

# Paginas publicas que deben compartir el mismo encabezado y pie.
PAGINAS_PUBLICAS = (
    'home', 'nosotros', 'servicios', 'planes',
    'contactos', 'simulador', 'opcion_user', 'pago',
)


class LayoutCompartidoTests(TestCase):
    """Marcas que solo puede poner base.html a traves de sus includes."""

    def test_todas_muestran_navbar_y_footer(self):
        for nombre in PAGINAS_PUBLICAS:
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()

                self.assertIn('class="nav-box"', html)
                self.assertIn('class="footer"', html)

    def test_el_layout_no_aparece_duplicado(self):
        """Copiar el layout ademas de heredarlo dibujaria dos navbars."""
        for nombre in PAGINAS_PUBLICAS:
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()

                self.assertEqual(html.count('<nav class="nav-box"'), 1)
                self.assertEqual(html.count('<footer class="footer"'), 1)

    def test_el_pie_dice_lo_mismo_en_todas(self):
        """Un solo pie de pagina implica un solo anio vigente."""
        for nombre in PAGINAS_PUBLICAS:
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()

                self.assertIn('2026 LBWUS', html)
                self.assertNotIn('&copy; 2024', html)

    def test_el_carrito_global_viaja_con_el_navbar(self):
        """El JS de planes llama a window.agregarAlCarrito desde el base."""
        for nombre in PAGINAS_PUBLICAS:
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()

                self.assertIn('id="cart-button"', html)
                self.assertIn('window.agregarAlCarrito', html)


class SimuladorHeredaTests(TestCase):
    """El simulador conserva sus funciones propias al heredar del base."""

    def setUp(self):
        self.html = self.client.get(reverse('simulador')).content.decode()

    def test_conserva_sus_dos_herramientas(self):
        self.assertIn('id="comunaInput"', self.html)
        self.assertIn('id="conversion-result"', self.html)

    def test_sigue_cargando_bootstrap(self):
        """Sus form-select y btn dependen de Bootstrap."""
        self.assertIn('bootstrap@5.3.3', self.html)

    def test_no_arrastra_el_css_que_pisaba_el_layout(self):
        """estilo.css define reglas globales (`*` y `body`) que romperian
        la tipografia y el modo oscuro del navbar y el footer compartidos.
        """
        # ManifestStaticFilesStorage puede agregar un hash al nombre:
        # simulador.01b5585786e9.css. La prueba acepta ambas formas.
        self.assertNotRegex(
            self.html,
            r'css/estilo(?:\.[0-9a-f]+)?\.css'
        )
        self.assertRegex(
            self.html,
            r'css/simulador(?:\.[0-9a-f]+)?\.css'
        )

    def test_su_css_queda_acotado_a_la_pagina(self):
        self.assertIn('class="simulador-page"', self.html)
