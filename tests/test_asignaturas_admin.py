"""Pantalla "Asignaturas" del admin (fase 4, commit 1): crear, renombrar y eliminar solo las que nadie usa.

Clase.asignatura es CASCADE: eliminar una en uso borraria sus clases y reservas. Datos ficticios.
"""

from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Clase
from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_especialidad import crear_profesor
from tests.test_especializaciones_revision import pdf
from tests.test_retiros import crear_admin, entrar_admin
from user_profesor import especializaciones


class AsignaturasAdminTests(TestCase):

    def setUp(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        self.algebra = Asignatura.objects.create(nombre='Álgebra')

    def post(self, nombre_url, datos=None, *args):
        return self.client.post(reverse(nombre_url, args=args), datos or {}, follow=True)

    def nombres(self):
        return list(Asignatura.objects.order_by('nombre').values_list('nombre', flat=True))

    def test_crea_con_el_nombre_limpio(self):
        r = self.post('crear_asignatura', {'nombre': '  Física   Cuántica '})
        self.assertContains(r, 'Asignatura «Física Cuántica» creada.')
        self.assertEqual(self.nombres(), ['Álgebra', 'Física Cuántica'])

    def test_no_crea_vacia_larga_ni_duplicada_aunque_cambien_las_mayusculas(self):
        for nombre, error in (('   ', 'Escribe el nombre'), ('x' * 61, 'hasta 60 caracteres'),
                              ('ÁLGEBRA', 'Ya existe la asignatura')):
            with self.subTest(nombre=nombre):
                self.assertContains(self.post('crear_asignatura', {'nombre': nombre}), error)
        self.assertEqual(self.nombres(), ['Álgebra'])

    def test_renombra_y_no_choca_con_otra(self):
        Asignatura.objects.create(nombre='Cálculo')
        self.assertContains(self.post('renombrar_asignatura', {'nombre': 'Algebra Lineal'}, self.algebra.pk),
                            '«Álgebra» ahora se llama «Algebra Lineal».')
        self.assertContains(self.post('renombrar_asignatura', {'nombre': 'cálculo'}, self.algebra.pk),
                            'Ya existe la asignatura')
        # Cambiar solo las mayusculas de la misma asignatura si se puede (no choca consigo misma).
        self.assertContains(self.post('renombrar_asignatura', {'nombre': 'ALGEBRA LINEAL'}, self.algebra.pk),
                            'ahora se llama «ALGEBRA LINEAL»')
        self.assertEqual(self.nombres(), ['ALGEBRA LINEAL', 'Cálculo'])

    def test_elimina_solo_si_nadie_la_usa(self):
        self.assertContains(self.post('eliminar_asignatura', {}, self.algebra.pk), 'Asignatura «Álgebra» eliminada.')
        self.assertEqual(self.nombres(), [])

    def test_no_elimina_una_con_clases(self):
        profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        Clase.objects.create(asignatura=self.algebra, modalidad='online', profesor=profesor)
        self.assertContains(self.post('eliminar_asignatura', {}, self.algebra.pk), 'está en uso')
        self.assertEqual(Clase.objects.count(), 1)

    def test_no_elimina_una_propuesta_en_una_especializacion(self):
        crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        especializaciones.subir(crear_profesor('20000000-1', 'profe@lbwus.cl', None), 'Diplomado', pdf('d.pdf'),
                                [self.algebra.pk])
        self.assertContains(self.post('eliminar_asignatura', {}, self.algebra.pk), 'está en uso')
        self.assertEqual(self.nombres(), ['Álgebra'])

    def test_la_pantalla_muestra_el_uso_y_solo_ofrece_eliminar_las_libres(self):
        libre = Asignatura.objects.create(nombre='Física')
        Clase.objects.create(asignatura=self.algebra, modalidad='online',
                             profesor=crear_profesor('20000000-1', 'profe@lbwus.cl', None))
        html = self.client.get(reverse('asignaturas_adm')).content.decode()
        self.assertIn('Catálogo (2)', html)
        self.assertIn(reverse('eliminar_asignatura', args=[libre.pk]), html)
        self.assertNotIn(reverse('eliminar_asignatura', args=[self.algebra.pk]), html)
        self.assertIn('En uso', html)

    def test_solo_el_admin(self):
        self.client.logout()
        entrar_soporte(self.client, crear_agente('10000003-5', lider=True))
        self.assertNotEqual(self.client.get(reverse('asignaturas_adm')).status_code, 200)
        self.client.post(reverse('crear_asignatura'), {'nombre': 'Física'})
        self.client.post(reverse('eliminar_asignatura', args=[self.algebra.pk]))
        self.assertEqual(self.nombres(), ['Álgebra'])
