"""El profesor propone una asignatura que no esta en el catalogo (fase 4, commit 2, decidido 07-nov).

Opcional, junto a las del catalogo: basta con marcar una de la lista o escribir otra. Se limpia como el
catalogo y, si ya esta en la lista (sin distinguir mayusculas), se le pide marcarla. El profesor y soporte
la ven marcada como "no esta en el catalogo". Datos ficticios.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Especialidad, Especializacion, Profesor
from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_especializaciones_subida import certificado
from user_profesor import especializaciones

NO_ESTA = '<em>(no está en el catálogo)</em>'


class OtraAsignaturaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.agente = crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        cls.algebra = Asignatura.objects.create(nombre='Álgebra')
        cls.profesor = crear_profesor('22222222-2', 'p@lbwus.cl', Especialidad.objects.create(nombre='Mate'),
                                      titulo_estado=Profesor.TITULO_PENDIENTE)

    def subir(self, ids, otra):
        return especializaciones.subir(self.profesor, 'Diplomado en Física', certificado(), ids, otra)

    def test_basta_con_otra_y_se_guarda_limpia(self):
        especializacion = self.subir([], '  Física   Moderna ')
        self.assertEqual(especializacion.otra_asignatura, 'Física Moderna')
        self.assertFalse(especializacion.propuestas.exists())
        self.assertEqual(self.profesor.tickets.get().categoria, Ticket.ESPECIALIZACIONES)  # soporte la revisa igual

    def test_junto_a_las_del_catalogo(self):
        especializacion = self.subir([self.algebra.pk], 'Física')
        self.assertEqual((list(especializacion.propuestas.all()), especializacion.otra_asignatura),
                         ([self.algebra], 'Física'))

    def test_sin_otra_queda_vacia(self):
        self.assertEqual(self.subir([self.algebra.pk], '   ').otra_asignatura, '')
        self.assertEqual(especializaciones.subir(self.profesor, 'Curso', certificado(),
                                                 [self.algebra.pk]).otra_asignatura, '')  # sin el argumento

    def test_errores_no_guardan_nada(self):
        casos = {
            'ninguna': ([], '', 'Elige al menos una asignatura de la lista o escribe otra.'),
            'ya esta en la lista': ([], 'ÁLGEBRA', '«ÁLGEBRA» ya está en la lista: márcala ahí.'),
            'larga': ([], 'x' * 61, 'hasta 60 caracteres'),
        }
        for caso, (ids, otra, mensaje) in casos.items():
            with self.subTest(caso), self.assertRaisesMessage(ValidationError, mensaje):
                self.subir(ids, otra)
        self.assertFalse(Especializacion.objects.exists())

    def test_llega_desde_el_formulario_y_el_profesor_la_ve(self):
        self.client.post(reverse('login'), {'username': '22222222-2', 'password': CLAVE})
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn('name="otra_asignatura"', html)
        self.assertIn('maxlength="60"', html)
        respuesta = self.client.post(reverse('subir_especializacion'), {
            'nombre': 'Diplomado en Física', 'otra_asignatura': 'Física', 'archivo': certificado()}).json()
        self.assertTrue(respuesta['success'], respuesta)
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn(f'Propones: Física {NO_ESTA}', html)  # sin coma suelta delante

    def test_soporte_la_ve_en_la_fila_junto_a_las_del_catalogo(self):
        self.subir([self.algebra.pk], '<b>Física</b>')
        entrar_soporte(self.client, self.agente)
        html = self.client.get(reverse('titulos_adm')).content.decode()
        self.assertIn(f'<td>Álgebra, &lt;b&gt;Física&lt;/b&gt; {NO_ESTA}', html)  # escapada
