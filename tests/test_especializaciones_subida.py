"""Subir especializaciones desde el portal del profesor (fase 2, commit 2, 06-nov).

Cada una: nombre, certificado cifrado y asignaturas propuestas del catalogo. Todas las pendientes van
al ticket de especializaciones del profesor (aparte del titulo). Maximo 5 en revision a la vez.
Se puede subir aunque el titulo aun no este aprobado. Datos ficticios.
"""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Especialidad, Especializacion, Profesor
from apoderados.documentos import ERROR_PDF_PAGINAS, descifrar
from soporte.models import Ticket
from tests.test_apoderados import crear_agente
from tests.test_apoderados_pdf import bytes_pdf
from tests.test_especialidad import CLAVE, crear_profesor
from user_profesor import especializaciones

PDF = bytes_pdf()


def certificado(contenido=PDF):
    return SimpleUploadedFile('certificado.pdf', contenido)


class SubirEspecializacionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.agente = crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        cls.algebra = Asignatura.objects.create(nombre='Álgebra')
        cls.calculo = Asignatura.objects.create(nombre='Cálculo')

    def setUp(self):
        self.profesor = crear_profesor('22222222-2', 'p@lbwus.cl', Especialidad.objects.create(nombre='Mate'),
                                       titulo_estado=Profesor.TITULO_PENDIENTE)

    def subir(self, nombre='Diplomado en Álgebra, U. de Chile', archivo='pdf', ids=None):
        archivo = certificado() if archivo == 'pdf' else archivo
        ids = [self.algebra.pk, self.calculo.pk] if ids is None else ids
        return especializaciones.subir(self.profesor, nombre, archivo, ids)

    def test_queda_en_revision_cifrada_con_sus_propuestas_y_en_su_ticket(self):
        especializacion = self.subir()
        self.assertEqual(especializacion.estado, Especializacion.EN_REVISION)
        self.assertEqual((descifrar(especializacion.contenido), especializacion.formato), (PDF, 'PDF'))
        self.assertEqual(set(especializacion.propuestas.all()), {self.algebra, self.calculo})
        ticket = self.profesor.tickets.get()  # su titulo esta pendiente: no hay ticket de titulo
        self.assertEqual((ticket.categoria, ticket.estado, ticket.asignado),
                         (Ticket.ESPECIALIZACIONES, Ticket.ABIERTO, self.agente))

    def test_varias_pendientes_van_al_mismo_ticket(self):
        self.subir()
        self.subir(nombre='Magíster en Matemática')
        self.assertEqual(self.profesor.especializaciones.count(), 2)
        self.assertEqual(self.profesor.tickets.filter(estado=Ticket.ABIERTO).count(), 1)

    def test_datos_invalidos_no_guardan_nada(self):
        casos = {
            'sin nombre': dict(nombre='   '),
            'nombre largo': dict(nombre='x' * 121),
            'sin asignaturas': dict(ids=[]),
            'asignatura inexistente': dict(ids=['999999']),
            'id manipulado': dict(ids=['abc', '²']),
            'una buena y una inexistente': dict(ids=[self.algebra.pk, '999999']),
            'sin archivo': dict(archivo=None),
        }
        for caso, datos in casos.items():
            with self.subTest(caso), self.assertRaises(ValidationError):
                self.subir(**datos)
        with self.assertRaisesMessage(ValidationError, ERROR_PDF_PAGINAS):
            self.subir(archivo=certificado(bytes_pdf(4)))
        self.assertFalse(Especializacion.objects.exists())
        self.assertFalse(Ticket.objects.exists())

    def test_maximo_5_en_revision_y_las_decididas_no_cuentan(self):
        for _ in range(Especializacion.MAX_EN_REVISION):
            self.subir()
        with self.assertRaisesMessage(ValidationError, 'Ya tienes 5 especializaciones en revisión'):
            self.subir()
        self.profesor.especializaciones.filter(pk=self.profesor.especializaciones.first().pk).update(
            estado=Especializacion.APROBADA)
        self.subir()  # ya hay cupo
        self.assertEqual(self.profesor.especializaciones.filter(estado=Especializacion.EN_REVISION).count(), 5)


class PanelEspecializacionesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        cls.algebra = Asignatura.objects.create(nombre='Álgebra')
        especialidad = Especialidad.objects.create(nombre='Mate')
        cls.profesor = crear_profesor('22222222-2', 'p@lbwus.cl', especialidad,
                                      titulo_estado=Profesor.TITULO_PENDIENTE)
        cls.otro = crear_profesor('33333333-3', 'o@lbwus.cl', especialidad)

    def setUp(self):
        self.client.post(reverse('login'), {'username': '22222222-2', 'password': CLAVE})

    def enviar(self, **cambios):
        datos = {'nombre': 'Diplomado en Álgebra', 'asignaturas': [self.algebra.pk], 'archivo': certificado()}
        return self.client.post(reverse('subir_especializacion'), {**datos, **cambios})

    def test_la_sube_desde_su_panel_aunque_su_titulo_no_este_aprobado(self):
        respuesta = self.enviar().json()
        self.assertTrue(respuesta['success'], respuesta)
        self.assertEqual(self.profesor.especializaciones.get().nombre, 'Diplomado en Álgebra')

    def test_un_error_vuelve_como_mensaje(self):
        respuesta = self.enviar(asignaturas=[]).json()
        self.assertEqual(respuesta, {'success': False, 'message': 'Elige al menos una asignatura de la lista.'})

    def test_solo_por_post_y_solo_el_profesor(self):
        self.assertEqual(self.client.get(reverse('subir_especializacion')).status_code, 405)
        self.client.logout()
        self.assertFalse(self.enviar().json()['success'])
        self.assertFalse(Especializacion.objects.exists())

    def test_el_panel_muestra_sus_especializaciones_y_el_catalogo(self):
        rechazada = Especializacion.objects.create(profesor=self.profesor, nombre='<b>Curso</b> ilegible',
                                                   estado=Especializacion.RECHAZADA, observacion='No se lee')
        rechazada.propuestas.set([self.algebra])
        Especializacion.objects.create(profesor=self.otro, nombre='Ajena')
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn('Mis especializaciones', html)
        self.assertIn('&lt;b&gt;Curso&lt;/b&gt; ilegible', html)  # escapado
        self.assertIn('Rechazada', html)
        self.assertIn('Motivo: <strong>No se lee</strong>', html)
        self.assertIn('Propones: Álgebra', html)
        self.assertIn(f'name="asignaturas" value="{self.algebra.pk}"', html)
        self.assertNotIn('Ajena', html)
        self.assertIn('id="form-especializacion"', html)

    def test_con_5_en_revision_el_formulario_se_reemplaza_por_un_aviso(self):
        Especializacion.objects.bulk_create(Especializacion(profesor=self.profesor, nombre=f'Curso {n}')
                                            for n in range(Especializacion.MAX_EN_REVISION))
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertNotIn('id="form-especializacion"', html)
        self.assertIn('Tienes 5 especializaciones en revisión', html)
