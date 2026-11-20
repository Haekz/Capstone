"""Correo de bienvenida al profesor que se registra (fase 1 del flujo de especialidades).

Dos caminos de registro: el formulario (regis_prof) y Google (CompletarRegistroGoogleForm).
El correo sale con transaction.on_commit: las pruebas ejecutan esos callbacks.
"""

from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from alumnos.google_forms import ALUMNO, PROFESOR, CompletarRegistroGoogleForm
from alumnos.models import Especialidad, Genero, Profesor
from tests.test_especialidad import CLAVE

CORREO = 'pedro@lbwus.cl'
ASUNTO = 'Te damos la bienvenida al equipo docente - LBWUS'


class BienvenidaProfesorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.especialidad = Especialidad.objects.create(nombre='Física')
        cls.genero = Genero.objects.create(descripcion='Otro')
        cls.datos = {
            'nombre': "Pedro O'Higgins", 'rut': '12345678-5',
            'especialidad': cls.especialidad.pk, 'direccion': 'Calle 1',
            'fecha_nacimiento': '1990-01-01', 'correo_electronico': CORREO, 'telefono': '911111111',
            'genero': cls.genero.id_genero,
            'password': CLAVE, 'confirm_password': CLAVE,
        }

    def registrar(self, **cambios):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('regis_prof'), {**self.datos, **cambios}).json()

    def registrar_con_google(self, tipo):
        form = CompletarRegistroGoogleForm({
            'tipo': tipo, 'nombre': 'Paula Google', 'rut': '12345678-5', 'telefono': '911111111',
            'direccion': 'Calle 1', 'fecha_nacimiento': '1990-01-01', 'genero': self.genero.pk,
            'especialidad': self.especialidad.pk, 'nivel_educacion': 'media',
        }, correo='paula@gmail.com')
        self.assertTrue(form.is_valid(), form.errors)
        with self.captureOnCommitCallbacks(execute=True):
            form.save()

    def test_al_registrarse_le_llega_la_bienvenida(self):
        self.assertTrue(self.registrar()['success'])
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual((correo.to, correo.subject), ([CORREO], ASUNTO))
        for texto in ("Hola Pedro O'Higgins,", 'aquí cada persona es importante', '"Sube tu título',
                      'Sube también tus especializaciones', 'Elige tus horarios', 'Equipo LBWUS'):
            self.assertIn(texto, correo.body)
        self.assertNotIn('&#x27;', correo.body)  # texto plano: sin entidades HTML
        self.assertNotIn('&quot;', correo.body)

    def test_si_el_registro_falla_no_se_envia_nada(self):
        self.assertFalse(self.registrar(rut='12345678-9')['success'])  # digito verificador incorrecto
        self.assertEqual(mail.outbox, [])

    def test_sin_servidor_de_correo_el_registro_igual_se_completa(self):
        with patch('alumnos.correo.send_mail', side_effect=OSError('sin servidor')), \
                self.assertLogs('alumnos.correo', 'ERROR'):
            self.assertTrue(self.registrar()['success'])
        self.assertTrue(Profesor.objects.filter(user__email=CORREO).exists())

    def test_el_profesor_que_se_registra_con_google_tambien_la_recibe(self):
        self.registrar_con_google(PROFESOR)
        self.assertEqual([(c.to, c.subject) for c in mail.outbox], [(['paula@gmail.com'], ASUNTO)])
        self.assertIn('Hola Paula Google,', mail.outbox[0].body)

    def test_el_alumno_que_se_registra_con_google_no_la_recibe(self):
        self.registrar_con_google(ALUMNO)
        self.assertEqual(mail.outbox, [])
