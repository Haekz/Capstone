"""Portal de admin, etapa A3: Resumen con el banner de pendientes, tarjetas clicables y Soporte en cifras en cuatro cifras.

Los pendientes del banner salen del servidor con los mismos criterios que la campana (admin_portal/avisos.py): la copia los contaba leyendo
secciones que aqui son paginas aparte. Datos ficticios.
"""
import re
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from admin_portal import metricas
from alumnos.models import SolicitudRetiro
from alumnos.roles import ADMIN
from resenas.models import ReporteResena
from soporte.models import Escalamiento, Ticket
from soporte.tickets import abrir_reporte
from tests.test_campana import avisos_de
from tests.test_resenas import BaseResenas, entrar
from tests.test_soporte_reportes import crear_alumno_adulto

DIAS = '(Lunes|Martes|Miércoles|Jueves|Viernes|Sábado|Domingo)'
MESES = '(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)'


class ResumenDelAdminTests(BaseResenas):

    def setUp(self):
        entrar(self.client, self.admin, ADMIN)
        self.adulto = crear_alumno_adulto()  # quien abre los tickets de los casos

    def pagina(self):
        return self.client.get(reverse('dashboard_admin')).content.decode()

    def pendientes(self):
        return {p['uno']: p['n'] for p in metricas.pendientes(metricas.soporte())}

    def ticket_de_otro(self, asunto='Cobro doble'):
        return abrir_reporte(self.adulto.user, Ticket.PAGOS, asunto, 'Detalle.')

    def test_sin_nada_pendiente_el_banner_lo_dice(self):
        self.assertEqual(set(self.pendientes().values()), {0})
        html = self.pagina()
        self.assertIn('Hola de nuevo, Tania', html)
        self.assertIn('No hay nada esperando tu decisión.', html)
        self.assertNotIn('adm-pend--hay', html)
        self.assertRegex(html, rf'id="adm-hoy">{DIAS}, \d{{1,2}} de {MESES}</span>')  # la fecha sale del servidor, en español

    def test_el_banner_cuenta_lo_que_espera_una_decision_del_admin(self):
        resena = self.resena(self.insc_paquete)
        for remitente in (self.bea, self.ana):  # dos reportes de una misma reseña cuentan una
            ReporteResena.objects.create(resena=resena, remitente=remitente.user, motivo='spam')
        ticket = self.ticket_de_otro()
        Escalamiento.objects.create(ticket=ticket, destino=Escalamiento.AL_ADMIN, motivo='Caso grave.')
        Escalamiento.objects.create(ticket=self.ticket_de_otro('Otro'), destino=Escalamiento.AL_LIDER, motivo='Del lider.')  # no es del admin
        Ticket.objects.filter(pk=ticket.pk).update(vence=timezone.now() - timedelta(days=1))
        for estado in (SolicitudRetiro.PENDIENTE, SolicitudRetiro.APROBADO, SolicitudRetiro.PAGADO, SolicitudRetiro.RECHAZADO):
            SolicitudRetiro.objects.create(profesor=self.profesor, monto=1000, estado=estado)  # solo los dos primeros esperan algo

        self.assertEqual(self.pendientes(), {'reseña reportada': 1, 'caso escalado': 1, 'retiro por pagar': 2, 'ticket atrasado': 1})
        html = self.pagina()
        self.assertIn('Tienes 5 pendientes que esperan tu decisión.', html)
        self.assertEqual(html.count('adm-pend--hay'), 4)
        for cifra in ('<strong>1</strong><span>reseña reportada</span>', '<strong>1</strong><span>caso escalado</span>',
                      '<strong>2</strong><span>retiros por pagar</span>', '<strong>1</strong><span>ticket atrasado</span>'):
            with self.subTest(cifra=cifra):
                self.assertIn(cifra, html)

    def test_el_banner_dice_lo_mismo_que_la_campana(self):
        resena = self.resena(self.insc_paquete)
        ReporteResena.objects.create(resena=resena, remitente=self.bea.user, motivo='spam')
        Escalamiento.objects.create(ticket=self.ticket_de_otro(), destino=Escalamiento.AL_ADMIN, motivo='Caso grave.')
        titulos = [aviso.titulo for aviso in avisos_de(admin_id=self.admin.id_tutor)]
        self.assertIn('1 reseña reportada', titulos)
        self.assertIn('1 caso escalado por soporte', titulos)
        self.assertEqual((self.pendientes()['reseña reportada'], self.pendientes()['caso escalado']), (1, 1))

    def test_cada_cifra_lleva_a_donde_se_resuelve(self):
        html = self.pagina()
        for destino in (reverse('resenas_moderacion'), reverse('casos_escalados'), '#finanzas', '#resumen'):
            with self.subTest(destino=destino):
                self.assertIn(f'<a href="{destino}" class="adm-pend', html)

    def test_las_tarjetas_llevan_a_su_seccion_y_dicen_lo_de_la_copia(self):
        html = self.pagina()
        self.assertEqual(re.findall(r'<div class="stat-card (\w+)" data-ir="(\w+)">', html),
                         [('purple', 'usuarios'), ('blue', 'usuarios'), ('green', 'clases')])
        for texto in ('Alumnos registrados', 'Profesores activos', 'Clases creadas', 'Últimos registros'):
            with self.subTest(texto=texto):
                self.assertIn(texto, html)
        for sobrante in ('Alumnos Registrados', 'Total en el sistema', 'stat-change'):
            with self.subTest(sobrante=sobrante):
                self.assertNotIn(sobrante, html)
        # El panel de Ultimos registros ya no lleva el margen en linea (lo da la capa): <div class="panel"> a secas
        self.assertRegex(html, r'<div class="panel">\s*<div class="panel-header">\s*<span class="panel-title">\s*'
                               r'<i class="bi bi-person-lines-fill"></i>\s*Últimos registros')

    def test_soporte_en_cifras_va_en_cuatro_cifras_y_con_la_tabla_aparte(self):
        html = self.pagina()
        self.assertEqual(re.findall(r'<li><strong>([^<]+)</strong><span>([^<]+)</span></li>', html),
                         [('0', 'abiertos'), ('0', 'atrasados'), ('sin datos', 'primera respuesta'), ('sin datos', 'cierre')])
        self.assertIn('<div class="soporte-tabla" style="overflow-x:auto;">', html)
        self.assertNotIn('primera respuesta: sin datos', html)  # el parrafo de antes
