"""La especialidad del profesor sale del catalogo, no de texto libre.

- El portal del alumno se caia con "Object of type Especialidad is not JSON
  serializable": profesores_js pasaba el objeto Especialidad a json_script.
- regis_prof y actualizar_perfil_prof hacian get_or_create con el texto del
  formulario, asi que cada profesor podia agregar especialidades al catalogo.
  Ahora reciben el id de una Especialidad existente y rechazan las demas.
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno, Especialidad, Genero, Profesor

User = get_user_model()

CLAVE = 'clave12345'
NAC = date(1990, 1, 1)


def crear_profesor(rut, email, especialidad, titulo_estado=Profesor.TITULO_APROBADO):
    u = User.objects.create_user(
        rut, password=CLAVE, rol='profesor', rut=rut, first_name='Profe',
        email=email, direccion='Calle 1', fecha_nacimiento=NAC,
        telefono='911111111', genero=Genero.objects.first(),
    )
    return Profesor.objects.create(user=u, especialidad=especialidad,
                                   titulo_estado=titulo_estado)


class PortalAlumnoEspecialidadTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        g = Genero.objects.create(descripcion='Otro')
        u = User.objects.create_user(
            '11111111-1', password=CLAVE, rol='alumno', rut='11111111-1',
            first_name='Ana', email='a@lbwus.cl', direccion='C1',
            fecha_nacimiento=NAC, genero=g,
        )
        Alumno.objects.create(user=u, nivel_educacion='media')
        cls.con = crear_profesor('22222222-2', 'p1@lbwus.cl',
                                 Especialidad.objects.create(nombre='Química'))
        cls.sin = crear_profesor('33333333-3', 'p2@lbwus.cl', None)

    def test_portal_responde_200_con_y_sin_especialidad(self):
        self.client.post(reverse('login'), {'username': '11111111-1', 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(r.status_code, 200)

        datos = {p['id']: p['specialties'] for p in r.context['profesores_js']}
        self.assertEqual(datos[self.con.id_profesor], ['Química'])
        self.assertEqual(datos[self.sin.id_profesor], [])
        # El JS lee los profesores desde json_script, no de un array armado
        # con {% for %} (que mostraba "None" y se rompia con comillas).
        self.assertContains(r, 'id="profesores-data"')
        self.assertContains(r, "JSON.parse(document.getElementById('profesores-data')")
        self.assertNotContains(r, 'const teachers = [')
        # json_script no escapa para innerHTML: los datos del profesor pasan
        # por escaparHtml y el onclick recibe el id, no el nombre.
        self.assertContains(r, '${escaparHtml(t.name)}')
        self.assertNotContains(r, "requestClassAccess('${t.name}')")


class RegistroProfesorEspecialidadTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')
        cls.fisica = Especialidad.objects.create(nombre='Física')
        cls.arte = Especialidad.objects.create(nombre='Arte')

    def _datos(self, especialidad):
        return {
            'nombre': 'Pedro Profe', 'rut': '12345678-5',
            'especialidad': especialidad, 'direccion': 'Calle 1',
            'fecha_nacimiento': '1990-01-01',
            'correo_electronico': 'pedro@lbwus.cl', 'telefono': '911111111',
            'genero': self.genero.id_genero,
            'password': CLAVE, 'confirm_password': CLAVE,
        }

    def test_formulario_muestra_catalogo_ordenado(self):
        r = self.client.get(reverse('regis_prof'))
        self.assertEqual(list(r.context['especialidades']), [self.arte, self.fisica])
        self.assertContains(r, '<select id="especialidad" name="especialidad"')
        self.assertContains(r, f'<option value="{self.fisica.pk}">Física</option>', html=True)

    def test_id_valido_guarda_la_especialidad_sin_crear_otra(self):
        antes = Especialidad.objects.count()
        r = self.client.post(reverse('regis_prof'), self._datos(self.fisica.pk))
        self.assertTrue(r.json()['success'], r.json())
        self.assertEqual(Profesor.objects.get(user__rut='12345678-5').especialidad, self.fisica)
        self.assertEqual(Especialidad.objects.count(), antes)

    def test_id_inexistente_o_texto_se_rechaza_sin_crear_nada(self):
        antes = Especialidad.objects.count()
        for valor in ['999999', 'Matemáticas', '-1', '²']:
            with self.subTest(valor=valor):
                r = self.client.post(reverse('regis_prof'), self._datos(valor))
                self.assertFalse(r.json()['success'])
                self.assertEqual(r.json()['message'], 'Selecciona una especialidad válida.')
        self.assertEqual(Especialidad.objects.count(), antes)
        self.assertFalse(User.objects.filter(rut='12345678-5').exists())
        self.assertFalse(Profesor.objects.exists())


class PerfilProfesorEspecialidadTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        Genero.objects.create(descripcion='Otro')
        cls.quimica = Especialidad.objects.create(nombre='Química')
        cls.historia = Especialidad.objects.create(nombre='Historia')
        cls.profesor = crear_profesor('22222222-2', 'p@lbwus.cl', cls.quimica)

    def setUp(self):
        self.client.post(reverse('login'), {'username': '22222222-2', 'password': CLAVE})

    def _datos(self, especialidad):
        u = self.profesor.user
        return {
            'nombre': u.first_name, 'rut': u.rut, 'especialidad': especialidad,
            'direccion': u.direccion, 'correo_electronico': u.email,
            'telefono': u.telefono, 'genero': u.genero.id_genero,
        }

    def test_panel_muestra_select_con_la_actual_seleccionada(self):
        r = self.client.get(reverse('panel_profesor'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(r.context['especialidades']), [self.historia, self.quimica])
        self.assertContains(
            r, f'<option value="{self.quimica.pk}" selected>Química</option>', html=True)
        self.assertContains(
            r, f'<option value="{self.historia.pk}">Historia</option>', html=True)

    def test_id_valido_actualiza_sin_crear_otra(self):
        antes = Especialidad.objects.count()
        r = self.client.post(reverse('actualizar_perfil_prof'), self._datos(self.historia.pk))
        self.assertTrue(r.json()['success'], r.json())
        self.profesor.refresh_from_db()
        self.assertEqual(self.profesor.especialidad, self.historia)
        self.assertEqual(Especialidad.objects.count(), antes)

    def test_id_inexistente_se_rechaza_sin_cambiar_nada(self):
        antes = Especialidad.objects.count()
        for valor in ['999999', 'Matemáticas']:
            with self.subTest(valor=valor):
                r = self.client.post(reverse('actualizar_perfil_prof'), self._datos(valor))
                self.assertFalse(r.json()['success'])
                self.assertEqual(r.json()['message'], 'Selecciona una especialidad válida.')
        self.profesor.refresh_from_db()
        self.assertEqual(self.profesor.especialidad, self.quimica)
        self.assertEqual(Especialidad.objects.count(), antes)
