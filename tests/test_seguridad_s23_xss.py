import html
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from alumnos.models import Genero, Alumno, Profesor, Especialidad

User = get_user_model()


class TestS23SeguridadXss(TestCase):
    """S-23: Sanear salida HTML y reducir superficies de ataque XSS (Cross-Site Scripting).
    
    Verifica que las interpolaciones dinámicas en Javascript y plantillas HTML
    (asignaturas, diálogos/modales y Buzón de mensajes) utilicen
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
        """Verifica que base.html declare window.escaparHtml de forma global contra XSS."""
        response = self.client.get(reverse('home'))
        contenido = response.content.decode('utf-8')

        # Declaración global de escaparHtml
        self.assertIn('function escaparHtml(str)', contenido)
        self.assertIn('window.escaparHtml = escaparHtml;', contenido)

    def test_catalogo_asignaturas_y_videos_sanean_campos_dinamicos(self):
        """Verifica que en el portal del alumno las asignaturas y videos escapen campos dinámicos."""
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()

        response = self.client.get(reverse('alumno_pag1'))
        contenido = response.content.decode('utf-8')

        # Profesores en dashboard
        self.assertIn('${escaparHtml(t.name)}', contenido)
        self.assertIn("${escaparHtml(t.specialties.join(', '))}", contenido)

        # Videos: el componente real (videos_apoyo.html) arma las tarjetas con textContent, nunca con innerHTML,
        # asi que titulo, materia y profesor que vienen del servidor no se interpretan como HTML.
        self.assertIn('nodo.textContent = texto', contenido)
        self.assertNotIn('boton.innerHTML', contenido)

    def test_buzon_alumno_y_profesor_escapan_nombres_y_mensajes(self):
        """El Buzon real (mensajes/panel.py) muestra nombres y textos escapados en ambos portales.

        Antes esta prueba buscaba lineas del chat de ejemplo en JS, que se reemplazo por el Buzon.
        """
        from mensajes.models import Conversacion, Mensaje

        texto_malicioso = '<img src=x onerror=alert(1)>'
        conversacion = Conversacion.objects.create(
            alumno=self.alumno, profesor=self.profesor, cliente=self.user_alumno)
        Mensaje.objects.create(conversacion=conversacion, autor=self.user_alumno, texto=texto_malicioso)

        # 1. Buzon del profesor: ve el nombre del alumno y su mensaje.
        self.client.force_login(self.user_prof)
        session = self.client.session
        session['profesor_id'] = self.profesor.id_profesor
        session.save()
        html_prof = self.client.get(reverse('panel_profesor'), {'c': conversacion.pk}).content.decode('utf-8')

        self.assertNotIn(texto_malicioso, html_prof)
        self.assertNotIn(self.user_alumno.first_name, html_prof)
        self.assertIn(html.escape(texto_malicioso, quote=False), html_prof)

        # 2. Buzon del alumno: ve su propio mensaje, tambien escapado.
        self.client.force_login(self.user_alumno)
        session = self.client.session
        session['alumno_id'] = self.alumno.id_alumno
        session.save()
        html_alum = self.client.get(reverse('alumno_pag1'), {'c': conversacion.pk}).content.decode('utf-8')

        self.assertNotIn(texto_malicioso, html_alum)
        self.assertNotIn(self.user_alumno.first_name, html_alum)

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

    def test_todos_los_dialogos_de_horarios_escapan_lo_que_interpolan(self):
        """LBW-11: el html de cada Swal.fire de horarios.js solo interpola variables safe* (ya escapadas)."""
        ruta = Path(settings.BASE_DIR) / 'alumnos/templates/alumnos/includes/panel/js/horarios.js'
        dialogos = re.findall(r'html:\s*`([^`]*)`', ruta.read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(dialogos), 2)  # reservar y reprogramar
        for dialogo in dialogos:
            for variable in re.findall(r'\$\{\s*([^}]*?)\s*\}', dialogo):
                with self.subTest(variable=variable):
                    self.assertTrue(variable.startswith('safe'), f'{variable} entra al html sin escapar')

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
