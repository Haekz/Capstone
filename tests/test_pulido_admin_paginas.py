"""Portal de admin, etapa A6: Planes, Casos escalados, Asignaturas, Nosotros y Reseñas con el marcado de la copia.

Cada pantalla pasa de estilos en linea a las clases de la capa (06c). Lo funcional (formularios, acciones, confirmaciones y datos reales como el
contacto) debe seguir igual: se prueba con datos. Datos ficticios.
"""
import re
from pathlib import Path

from django.urls import reverse

from alumnos.models import Asignatura
from alumnos.roles import ADMIN
from resenas.models import ReporteResena
from soporte.models import Escalamiento, Ticket
from soporte.tickets import abrir_reporte
from tests.test_resenas import BaseResenas, entrar
from tests.test_soporte_reportes import crear_alumno_adulto

STATIC = Path(__file__).resolve().parent.parent / 'admin_portal/static/admin_portal'


class PaginasDelAdminTests(BaseResenas):

    def setUp(self):
        entrar(self.client, self.admin, ADMIN)

    def pagina(self, nombre):
        return self.client.get(reverse(nombre)).content.decode()

    def test_ninguna_pantalla_conserva_el_margen_de_28px_en_linea(self):
        for nombre in ('planes_adm', 'casos_escalados', 'asignaturas_adm', 'resenas_moderacion'):
            with self.subTest(pagina=nombre):
                self.assertNotIn('margin-top:28px', self.pagina(nombre))

    # ── Planes ──
    def test_planes_intro_con_la_clase_de_la_capa(self):
        html = self.pagina('planes_adm')
        self.assertRegex(html, r'<p class="adm-panel-intro">\s*La clase suelta cuesta \$[\d.]+, igual con todos los profesores')
        self.assertNotIn('<p class="stat-sub" style=', html)
        self.assertEqual(html.count('<div class="stat-card">'), 3)  # los 3 planes siguen ahi
        self.assertEqual(re.findall(r'<th scope="row">([^<]+)</th>', html), ['Flexible', 'Progreso', 'Intensivo'])

    def test_planes_va_en_su_seccion_como_en_la_copia(self):
        """06b pide #section-planes > .stats-grid (tres columnas) y admin-section active da el gap entre las tarjetas y el panel.

        Solo con el id, el contenedor es un div sin gap; con admin-section pero sin active, queda oculto (display:none).
        """
        html = self.pagina('planes_adm')
        self.assertRegex(html, r'<div id="section-planes" class="admin-section active">\s*<div class="stats-grid">')  # hijo directo
        capa = (STATIC / 'css/admin_panel/06b_pulido_admin_resumen.css').read_text(encoding='utf-8')
        self.assertIn('#portal-admin #section-planes > .stats-grid', capa)
        base = (STATIC / 'css/admin_panel/02_componentes.css').read_text(encoding='utf-8')
        self.assertRegex(base, r'\.admin-section \{\s*display: none;\s*flex-direction: column;\s*gap: 24px;')
        self.assertRegex(base, r'\.admin-section\.active \{\s*display: flex;')

    # ── Casos escalados ──
    def test_escalados_vacio_con_su_aviso_en_caja(self):
        html = self.pagina('casos_escalados')
        self.assertIn('<div class="panel-body">', html)
        self.assertIn('<p class="adm-panel-intro adm-panel-intro--dentro">Ves el asunto y los motivos.', html)
        self.assertIn('<p class="adm-vacio">No hay casos esperando tu indicación.</p>', html)
        self.assertNotIn('padding:18px', html)

    def test_escalados_con_un_caso_sigue_pidiendo_la_indicacion(self):
        ticket = abrir_reporte(crear_alumno_adulto().user, Ticket.PAGOS, 'Cobro doble', 'Detalle.')
        escalamiento = Escalamiento.objects.create(ticket=ticket, destino=Escalamiento.AL_ADMIN, motivo='Caso grave.')
        html = self.pagina('casos_escalados')
        self.assertIn('Esperan tu indicación (1)', html)
        self.assertIn(reverse('indicar_escalado', args=[escalamiento.pk]), html)
        self.assertIn(f'<textarea id="indicacion-{escalamiento.pk}" name="indicacion"', html)
        self.assertNotIn('No hay casos esperando tu indicación.', html)

    # ── Asignaturas ──
    def test_asignaturas_formularios_con_las_clases_de_la_capa(self):
        html = self.pagina('asignaturas_adm')
        self.assertIn(f'<form method="post" action="{reverse("crear_asignatura")}" class="adm-form-linea">', html)
        self.assertIn('<label for="nueva-asignatura" class="form-label">Nombre</label>', html)
        self.assertRegex(html, r'id="nueva-asignatura" name="nombre" maxlength="\d+" required placeholder="Ej\.: Física" class="form-input">')
        self.assertRegex(html, r'class="adm-form-linea adm-form-linea--tabla">\s*<input type="hidden"[^>]*>\s*<input type="text" name="nombre" '
                               r'value="Álgebra"[^>]*class="form-input">')
        self.assertNotIn('border-radius:8px', html)  # ya no hay campos con el estilo en linea

    def test_asignatura_en_uso_con_candado_y_la_libre_se_puede_eliminar_con_su_confirmacion(self):
        libre = Asignatura.objects.create(nombre='Química')
        html = self.pagina('asignaturas_adm')
        self.assertIn('<small class="adm-nota"><i class="bi bi-lock" aria-hidden="true"></i> En uso (clases o especializaciones)</small>', html)
        self.assertEqual(html.count('En uso (clases o especializaciones)'), 1)  # Algebra esta en uso; Quimica no
        self.assertIn(reverse('eliminar_asignatura', args=[libre.pk]), html)
        self.assertIn("confirm('¿Eliminar «Química»?')", html)

    # ── Nosotros ──
    def test_nosotros_en_cuatro_bloques_con_el_contacto_real(self):
        html = self.pagina('nosotros_adm')
        self.assertIn('<div class="nos-grid">', html)
        self.assertEqual(re.findall(r'<div class="info-block nos-bloque (nos-bloque--\w+)">\s*<h3><i class="bi ([\w-]+)" aria-hidden="true"></i> ([^<]+)</h3>', html),
                         [('nos-bloque--mision', 'bi-bullseye', 'Misión'), ('nos-bloque--vision', 'bi-eye-fill', 'Visión'),
                          ('nos-bloque--valores', 'bi-gem', 'Valores'), ('nos-bloque--datos', 'bi-bar-chart-fill', 'Datos del equipo')])
        self.assertIn('<div class="nos-datos">', html)
        self.assertIn('conectándolos con los mejores profesores particulares', html)  # el texto no cambia, solo las etiquetas
        self.assertRegex(html, r'<span>Contacto</span><strong>[^<@\s]+@[^<\s]+</strong>')  # el correo sale de la configuracion, no de la copia
        self.assertNotIn('teachers@lbwus.cl', html)
        for estilo in ('color:#f59e0b', 'color:#10b981', 'color:#3b82f6', 'grid-template-columns:1fr 1fr'):
            with self.subTest(estilo=estilo):
                self.assertNotIn(estilo, html)

    # ── Reseñas ──
    def test_resenas_con_una_reportada_sigue_ofreciendo_mantener_u_ocultar(self):
        resena = self.resena(self.insc_paquete, comentario='Texto reportado')
        ReporteResena.objects.create(resena=resena, remitente=self.bea.user, motivo='spam')
        html = self.pagina('resenas_moderacion')
        self.assertIn('Reportadas pendientes (1)', html)
        self.assertIn(reverse('resena_moderar', args=[resena.pk]), html)
        for accion in ('mantener', 'ocultar'):
            with self.subTest(accion=accion):
                self.assertIn(f'name="accion" value="{accion}"', html)
        self.assertEqual(html.count('<div class="panel">'), 3)
