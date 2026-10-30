import html
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from alumnos.models import Genero, Alumno, Profesor, Especialidad

User = get_user_model()


class TestS23SeguridadXss(TestCase):
    """S-23: Sanear salida HTML y reducir superficies de ataque XSS (Cross-Site Scripting).
    
    Verifica que las interpolaciones dinámicas en Javascript y plantillas HTML
    (asignaturas, diálogos/modales, carrito de compras y chat) utilicen
    escape contextual estricto o APIs DOM seguras (textContent, dataset),
    neutralizando vectores de inyección con caracteres especiales (&, <, >, ", ').
    """

    @classmethod
    def setUpTestData(cls):
        cls.genero = Genero.objects.create(descripcion='Otro')
        cls.especialidad = Especialidad.objects.create(nombre='Matemáticas')

        # Alumno con payload especial simulado
        cls.user_alumno = User.objects.create_user(
            username='12345678-5',
            rut='12345678-5',
            email='alumno_xss@test.cl',
            first_name='<script>alert("XSS")</script>',
            last_name='O\'Connor "Tester"',
            password='Password123!',
            rol='alumno',
            genero=cls.genero
        )
        cls.alumno = Alumno.objects.create(user=cls.user_alumno)

        # Profesor
        cls.user_prof = User.objects.create_user(
            username='22222222-2',
            rut='22222222-2',
            email='prof_xss@test.cl',
            first_name='Profesor Seguro',
            password='Password123!',
            rol='profesor',
            genero=cls.genero
        )
        cls.profesor = Profesor.objects.create(user=cls.user_prof, especialidad=cls.especialidad)

    def test_base_html_incluye_escapar_html_global_y_carrito_seguro(self):
        """Verifica que base.html declare window.escaparHtml y sanee el carrito de compras."""
        response = self.client.get(reverse('home'))
        contenido = response.content.decode('utf-8')

        # Declaración global de escaparHtml
        self.assertIn('function escaparHtml(str)', contenido)
        self.assertIn('window.escaparHtml = escaparHtml;', contenido)

        # Carrito con escape contextual contra XSS en item.titulo e item.id
        self.assertIn('escaparHtml(item.titulo)', contenido)
        self.assertIn('escaparHtml(item.id)', contenido)
        self.assertIn('window.agregarAlCarrito', contenido)

    def test_catalogo_asignaturas_y_videos_sanean_campos_dinamicos(self):
        """Verifica que en el portal del alumno las asignaturas y videos escapen campos dinámicos."""
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()

        response = self.client.get(reverse('alumno_pag1'))
        contenido = response.content.decode('utf-8')

        # Cursos / Asignaturas
        self.assertIn('const safeTitle = escaparHtml(c.title);', contenido)
        self.assertIn('const safeAuthor = escaparHtml(c.author);', contenido)
        self.assertIn('const safeColor = escaparHtml(c.color);', contenido)

        # Videos
        self.assertIn('${escaparHtml(v.title)}', contenido)
        self.assertIn('${escaparHtml(v.specialty)}', contenido)
        self.assertIn('${escaparHtml(v.teacher)}', contenido)

    def test_chat_alumno_y_profesor_sanean_mensajes_y_contactos(self):
        """Verifica que los chats (alumno y profesor) escapen nombres, cursos y textos."""
        # 1. Chat alumno
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()
        resp_alum = self.client.get(reverse('alumno_pag1'))
        html_alum = resp_alum.content.decode('utf-8')

        self.assertIn('const safeTeacherName = escaparHtml(chat.teacherName);', html_alum)
        self.assertIn('const safeSpecialty = escaparHtml(chat.specialty);', html_alum)
        self.assertIn('const safeLastText = escaparHtml(lastMsg ? lastMsg.text : \'\');', html_alum)

        # 2. Chat profesor
        self.client.force_login(self.user_prof)
        session = self.client.session
        session['profesor_id'] = self.profesor.id_profesor
        session.save()
        resp_prof = self.client.get(reverse('panel_profesor'))
        html_prof = resp_prof.content.decode('utf-8')

        self.assertIn('const safeStudentName = escHtml(chat.studentName);', html_prof)
        self.assertIn('const safeCourseName = escHtml(chat.courseName);', html_prof)
        self.assertIn('const safeLastText = escHtml(lastMsg ? lastMsg.text : \'\');', html_prof)
        self.assertIn('<strong>${escFn(msg.name)}:</strong> <span>${escFn(msg.text)}</span>', html_prof)

    def test_dialogos_y_reserva_sesiones_usan_dataset_y_escape_contextual(self):
        """Verifica que la reserva de horarios use dataset y escape en diálogos SweetAlert."""
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()

        response = self.client.get(reverse('alumno_pag1'))
        contenido = response.content.decode('utf-8')

        # No debe usar interpolación inline onclick con comillas javascript vulnerables
        self.assertNotIn("onclick=\"confirmarReservaSesion(${s.id_sesion}, '${s.asignatura.replace(/'/g", contenido)

        # Debe usar dataset desacoplado y seguro
        self.assertIn('data-asig="${safeAsignatura}"', contenido)
        self.assertIn('btn-reservar-sesion', contenido)
        self.assertIn('this.dataset.asig', contenido)

        # El modal de diálogo debe escapar el nombre de la asignatura
        self.assertIn('safeAsig', contenido)
        self.assertIn('escaparHtml(nombreAsignatura)', contenido)

    def test_busqueda_global_admin_sanea_query_y_elimina_mocks_estaticos(self):
        """Verifica que la búsqueda en el portal admin no refleje queries sin escapar."""
        self.client.force_login(self.user_prof)
        response = self.client.get(reverse('home'))
        # Verificar en base_admin.html
        with open('admin_portal/templates/admin_portal/base_admin.html', 'r', encoding='utf-8') as f:
            contenido_admin = f.read()

        self.assertIn('No se encontraron secciones para "<strong>${esc(query)}</strong>"', contenido_admin)
        self.assertNotIn('Francheska (Alumno)', contenido_admin)
        self.assertNotIn('Franco (Profesor)', contenido_admin)

    def test_pago_html_sanea_campos_de_planes_y_carrito(self):
        """Verifica que pago.html sanee los títulos de planes contra XSS en localStorage."""
        self.client.force_login(self.user_alumno)
        response = self.client.get(reverse('pago'))
        contenido = response.content.decode('utf-8')

        self.assertIn('esc(it.titulo)', contenido)
        self.assertIn('esc(pObj.label)', contenido)
