'El layout comun debe salir una sola vez y en todas las paginas publicas.\n\nNavbar y footer viven en alumnos/templates/alumnos/includes/. Estos tests\ndetectan tanto una copia pegada a mano como un include roto.\n'
from django.test import TestCase
from django.urls import reverse
PAGINAS_PUBLICAS = ('home', 'nosotros', 'servicios', 'planes', 'contactos', 'opcion_user')

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

    def test_no_queda_carrito_de_compras(self):
        """Los paquetes se compran directo en Planes: el carrito (localStorage) ya no existe."""
        for nombre in PAGINAS_PUBLICAS:
            with self.subTest(pagina=nombre):
                html = self.client.get(reverse(nombre)).content.decode()
                self.assertNotIn('id="cart-button"', html)
                self.assertNotIn('agregarAlCarrito', html)


class SimuladorRetiradoTests(TestCase):
    """Tenia profesores inventados y un conversor sin uso; la busqueda real esta en el portal del alumno."""

    def test_la_pagina_ya_no_existe(self):
        self.assertEqual(self.client.get('/alumnos/simulador').status_code, 404)
