from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from alumnos.models import Alumno, Profesor, Clase, Asignatura, Especialidad, Genero

User = get_user_model()

class IntegracionFlujosTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.genero = Genero.objects.create(descripcion='Masculino')
        self.especialidad = Especialidad.objects.create(nombre='Física')
        self.asignatura = Asignatura.objects.create(nombre='Física Cuántica')

        # Usuario Profesor
        self.user_profesor = User.objects.create_user(
            username='12345678-9',
            rut='12345678-9',
            email='profe@test.com',
            password='securepassword'
        )
        self.profesor = Profesor.objects.create(
            user=self.user_profesor,
            especialidad=self.especialidad
        )

        # Clase
        self.clase = Clase.objects.create(
            profesor=self.profesor,
            asignatura=self.asignatura,
            modalidad='online',
            horario='10:00'
        )

        # Usuario Alumno
        self.user_alumno = User.objects.create_user(
            username='98765432-1',
            rut='98765432-1',
            email='alumno@test.com',
            password='securepassword'
        )
        self.alumno = Alumno.objects.create(
            user=self.user_alumno,
            nivel_educacion='Universitaria'
        )

    def test_flujo_transmision_en_vivo(self):
        '''Prueba que el profesor puede iniciar directo y cambiar el estado en_vivo.'''
        # Verificar estado inicial
        self.assertFalse(self.clase.en_vivo)
        
        # Loguear como profesor simulando la sesion
        self.client.force_login(self.user_profesor)
        session = self.client.session
        session['profesor_id'] = self.profesor.id_profesor
        session.save()

        # Enviar POST para iniciar directo
        response = self.client.post(
            reverse('iniciar_directo', args=[self.clase.id_clase]),
            {'descripcion_vivo': 'Hoy veremos relatividad', 'temas_vivo': 'Teoría, Ecuaciones'}
        )
        
        # Debe responder JSON success: True
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        # Verificar base de datos actualizada
        self.clase.refresh_from_db()
        self.assertTrue(self.clase.en_vivo)
        self.assertEqual(self.clase.descripcion_vivo, 'Hoy veremos relatividad')
        self.assertEqual(self.clase.temas_vivo, 'Teoría, Ecuaciones')

    def test_transmision_rechaza_no_autorizado(self):
        '''Prueba que un alumno NO puede iniciar directo en la clase del profe.'''
        # Loguear como alumno
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()

        response = self.client.post(
            reverse('iniciar_directo', args=[self.clase.id_clase]),
            {'descripcion_vivo': 'Hack', 'temas_vivo': 'Hack'}
        )
        
        # Debe responder success: False (No autorizado)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['success'])
        
        self.clase.refresh_from_db()
        self.assertFalse(self.clase.en_vivo)

    def test_autenticacion_unificada(self):
        '''Prueba el RutOrEmailBackend con distintas variaciones de login.'''
        from django.contrib.auth import authenticate
        
        # 1. Login con RUT limpio (solo guion)
        user = authenticate(username='12345678-9', password='securepassword')
        self.assertIsNotNone(user)
        self.assertEqual(user.username, '12345678-9')

        # 2. Login con RUT formateado (con puntos)
        user = authenticate(username='12.345.678-9', password='securepassword')
        self.assertIsNotNone(user)

        # 3. Login con Email
        user = authenticate(username='profe@test.com', password='securepassword')
        self.assertIsNotNone(user)

    def test_integracion_customuser_cascada(self):
        '''Prueba la integridad referencial al borrar un CustomUser.'''
        profe_id = self.profesor.id_profesor
        self.assertTrue(Profesor.objects.filter(pk=profe_id).exists())
        
        # Al borrar el usuario central...
        self.user_profesor.delete()
        
        # El perfil satélite (Profesor) debe borrarse automáticamente (CASCADE)
        self.assertFalse(Profesor.objects.filter(pk=profe_id).exists())

