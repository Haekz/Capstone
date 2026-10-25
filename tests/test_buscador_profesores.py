"""Buscador de profesores del portal del alumno (alumno_pag1).

- Solo aparecen profesores con titulo aprobado, con nombre y especialidad
  reales (el buscador filtra por esos dos campos).
- No se envian metricas inventadas: distancia, calificacion y precio estaban
  fijos en el codigo para todos los profesores.
- Los datos del profesor salen escapados y la lista vacia no rompe el portal.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno, Especialidad, Genero, Profesor
from tests.test_especialidad import CLAVE, NAC, crear_profesor

User = get_user_model()

RUT_ALUMNO = '11111111-1'


def crear_profesor_con_nombre(rut, nombre, apellido, especialidad=None,
                              titulo_estado=Profesor.TITULO_APROBADO):
    profesor = crear_profesor(rut, f'{rut}@lbwus.cl', especialidad, titulo_estado)
    profesor.user.first_name = nombre
    profesor.user.last_name = apellido
    profesor.user.save(update_fields=['first_name', 'last_name'])
    return profesor


class BuscadorProfesoresTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        u = User.objects.create_user(
            RUT_ALUMNO, password=CLAVE, rol='alumno', rut=RUT_ALUMNO,
            first_name='Ana', email='alumna@lbwus.cl', direccion='C1',
            fecha_nacimiento=NAC, genero=genero,
        )
        Alumno.objects.create(user=u, nivel_educacion='media')
        cls.matematicas = Especialidad.objects.create(nombre='Matemáticas')

    def setUp(self):
        self.client.post(reverse('login'), {'username': RUT_ALUMNO, 'password': CLAVE})

    def _portal(self):
        r = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(r.status_code, 200)
        return r

    def test_solo_aparecen_profesores_con_titulo_aprobado(self):
        aprobado = crear_profesor_con_nombre('20000000-1', 'Carla', 'Aprobada')
        for i, estado in enumerate([Profesor.TITULO_PENDIENTE,
                                    Profesor.TITULO_EN_REVISION,
                                    Profesor.TITULO_RECHAZADO]):
            crear_profesor_con_nombre(f'2000000{i + 2}-1', 'Oculto', estado,
                                      titulo_estado=estado)

        r = self._portal()
        ids = [p['id'] for p in r.context['profesores_js']]
        self.assertEqual(ids, [aprobado.id_profesor])
        self.assertEqual(len(r.context['profesores_list']), 1)
        self.assertNotContains(r, 'Oculto')

    def test_entrega_nombre_y_especialidad_reales_sin_metricas_simuladas(self):
        p = crear_profesor_con_nombre('20000000-1', 'Carla', 'Rojas', self.matematicas)

        r = self._portal()
        self.assertEqual(r.context['profesores_js'], [{
            'id': p.id_profesor,
            'name': 'Carla Rojas',
            'specialties': ['Matemáticas'],
            'initial': 'C',
        }])
        # Ni en los datos ni en las tarjetas que arma el JS.
        self.assertNotContains(r, '5.0 ⭐')
        for metrica in ('"distance"', '"rating"', '"price"',
                        '${t.distance}', '${t.rating}', 'a.distance - b.distance'):
            self.assertNotContains(r, metrica)

    def test_profesores_ordenados_por_nombre(self):
        crear_profesor_con_nombre('20000000-1', 'Zoe', 'Mora')
        crear_profesor_con_nombre('20000000-2', 'Bruno', 'Díaz')
        crear_profesor_con_nombre('20000000-3', 'Bruno', 'Arce')

        nombres = [p['name'] for p in self._portal().context['profesores_js']]
        self.assertEqual(nombres, ['Bruno Arce', 'Bruno Díaz', 'Zoe Mora'])

    def test_datos_del_profesor_salen_escapados(self):
        malicioso = '<img src=x onerror=alert(1)>'
        especialidad = Especialidad.objects.create(nombre='<script>x</script>')
        crear_profesor_con_nombre('20000000-1', malicioso, '', especialidad)

        r = self._portal()
        # El dato llega intacto a la vista, pero json_script lo escapa en el HTML.
        self.assertEqual(r.context['profesores_js'][0]['name'], malicioso)
        self.assertNotContains(r, malicioso)
        self.assertNotContains(r, '<script>x</script>')
        self.assertContains(r, '\\u003Cimg src=x onerror=alert(1)\\u003E')
        # Las tarjetas pasan nombre y especialidad por escaparHtml.
        self.assertNotContains(r, '${t.name}')
        self.assertNotContains(r, '${t.specialties')

    def test_sin_profesores_aprobados_el_portal_muestra_lista_vacia(self):
        for caso in ('sin profesores', 'solo uno pendiente'):
            with self.subTest(caso=caso):
                if caso == 'solo uno pendiente':
                    crear_profesor_con_nombre('20000000-1', 'Pendiente', 'Uno',
                                              titulo_estado=Profesor.TITULO_PENDIENTE)
                r = self._portal()
                self.assertEqual(r.context['profesores_js'], [])
                self.assertContains(
                    r, '<script id="profesores-data" type="application/json">[]</script>',
                    html=False)
                self.assertContains(r, 'No hay profesores que coincidan con tu búsqueda.')

    def test_tutores_y_videos_de_ejemplo_estan_identificados(self):
        r = self._portal()
        self.assertContains(r, 'Contenido de ejemplo: aún no hay tutores registrados')
        self.assertContains(r, 'Contenido de ejemplo: aún no hay clases en video')
