"""Portal de admin, etapa A5: Finanzas (dos grupos con nota por tarjeta), Clases y Ajustes con los textos de la copia.

Lo importante en Finanzas: las tarjetas se reordenaron y cambiaron de nombre; cada rotulo debe seguir mostrando SU dato. Datos ficticios.
"""
import re

from django.urls import reverse

from alumnos.models import SolicitudRetiro
from alumnos.roles import ADMIN
from tests.test_resenas import BaseResenas, entrar

TARJETA = re.compile(r'<div class="stat-label">([^<]+)</div>\s*<div class="stat-value">([^<]+)</div>\s*<div class="stat-sub">([^<]+)</div>')


class PantallasDelAdminTests(BaseResenas):

    def setUp(self):
        entrar(self.client, self.admin, ADMIN)

    def pagina(self):
        return self.client.get(reverse('dashboard_admin')).content.decode()

    # ── Finanzas ──
    def test_finanzas_en_dos_grupos_con_titulo(self):
        html = self.pagina()
        self.assertEqual(re.findall(r'<h2 class="fin-grupo-titulo">([^<]+)</h2>', html), ['Ingresos de la plataforma', 'Pagos a profesores'])
        self.assertEqual(re.findall(r'<div class="stats-grid (fin-grid[^"]*)">', html), ['fin-grid', 'fin-grid fin-grid--3'])

    def test_finanzas_cada_tarjeta_con_su_rotulo_su_nota_y_su_dato(self):
        SolicitudRetiro.objects.create(profesor=self.profesor, monto=1000, estado=SolicitudRetiro.PENDIENTE)
        SolicitudRetiro.objects.create(profesor=self.profesor, monto=2500, estado=SolicitudRetiro.PAGADO)
        tarjetas = {rotulo: (valor, nota) for rotulo, valor, nota in TARJETA.findall(self.pagina())}
        self.assertEqual(list(tarjetas), ['Cobrado', 'Por dictar o entregar', 'Comisión estimada', 'Ganancia LBWUS',
                                          'Retiros pendientes', 'Retiros pagados', 'Saldo sin pedir'])
        self.assertEqual(tarjetas['Retiros pendientes'], ('$1.000', 'Esperan que los pagues'))
        self.assertEqual(tarjetas['Retiros pagados'], ('$2.500', 'Total transferido'))
        self.assertEqual({rotulo: nota for rotulo, (_, nota) in tarjetas.items()}, {
            'Cobrado': 'Pagos aprobados, sin lo devuelto', 'Por dictar o entregar': 'Aún no es ingreso',
            'Comisión estimada': '15 % de clases y 25 % de videos, si se entrega todo',
            'Ganancia LBWUS': '15 % de clases dictadas y 25 % de videos compartidos',
            'Retiros pendientes': 'Esperan que los pagues', 'Retiros pagados': 'Total transferido',
            'Saldo sin pedir': 'Disponible de los profesores, aún sin solicitar'})

    def test_finanzas_los_retiros_aprobados_siguen_esperando_pago(self):
        SolicitudRetiro.objects.create(profesor=self.profesor, monto=4000, estado=SolicitudRetiro.APROBADO)
        tarjetas = {rotulo: valor for rotulo, valor, _ in TARJETA.findall(self.pagina())}
        self.assertEqual((tarjetas['Retiros pendientes'], tarjetas['Retiros pagados']), ('$4.000', '$0'))

    def test_finanzas_tabla_vacia_con_los_textos_de_la_copia(self):
        html = self.pagina()
        self.assertIn('<i class="bi bi-card-list"></i> Solicitudes de retiro</span>', html)
        self.assertIn('<th>Fecha de solicitud</th>', html)
        self.assertIn('<p>No hay solicitudes de retiro. Cuando un profesor pida un retiro, aparecerá aquí.</p>', html)
        for viejo in ('Solicitudes de Retiro', 'Fecha Solicitud', 'registradas en el sistema', 'Retiros Pagados', 'Retiros Pendientes'):
            with self.subTest(viejo=viejo):
                self.assertNotIn(viejo, html)

    def test_finanzas_con_retiros_la_tabla_no_cambia_de_logica(self):
        retiro = SolicitudRetiro.objects.create(profesor=self.profesor, monto=1000, estado=SolicitudRetiro.PENDIENTE)
        html = self.pagina()
        self.assertIn(reverse('aprobar_retiro', args=[retiro.pk]), html)  # las acciones siguen ahi
        self.assertIn(reverse('rechazar_retiro', args=[retiro.pk]), html)
        self.assertNotIn('No hay solicitudes de retiro.', html)

    # ── Clases ──
    def test_clases_materia_y_solo_lectura(self):
        html = self.pagina()
        self.assertIn('<p class="adm-panel-intro">Las asigna soporte al aprobar el título o una especialización de cada profesor. '
                      'Solo lectura.</p>', html)
        self.assertRegex(html, r'<th>#</th>\s*<th>Materia</th>\s*<th>Profesor</th>\s*<th>Modalidad</th>')
        self.assertNotIn('Curso / Materia', html)
        self.assertIn('<strong>Álgebra</strong>', html)  # la clase de la prueba sigue apareciendo

    # ── Ajustes ──
    def test_ajustes_textos_de_la_copia_y_datos_del_admin(self):
        html = self.pagina()
        self.assertIn('<div class="panel adm-panel-angosto">', html)
        self.assertIn('<i class="bi bi-gear-fill"></i> Tus datos</span>', html)
        # Los textos de la copia, cada etiqueta asociada a su campo (20-nov: antes no tenian for ni el campo id)
        for campo, etiqueta in (('nombre', 'Nombre'), ('correo', 'Correo electrónico'), ('telefono', 'Teléfono'),
                                ('direccion', 'Dirección')):
            with self.subTest(etiqueta=etiqueta):
                self.assertIn(f'<label class="form-label" for="ajustes-{campo}">{etiqueta}</label>', html)
        self.assertIn('<label class="form-label" for="ajustes-rut">RUT <span class="adm-nota">(no se puede cambiar)</span>'
                      '</label>', html)
        self.assertIn('<label class="form-label" for="accent-color-select">Color de acento del panel '
                      '<span class="adm-nota">(solo esta sesión)</span></label>', html)
        for opcion in ('Morado LBWUS (por defecto)', 'Azul océano', 'Verde menta'):
            with self.subTest(opcion=opcion):
                self.assertIn(f'>{opcion}</option>', html)
        self.assertRegex(html, r'<div class="form-actions">\s*<button type="submit" class="btn-primary">\s*'
                               r'<i class="bi bi-save"></i> Guardar cambios')
        self.assertIn('value="Tania"', html)  # siguen siendo los datos del administrador
        self.assertIn('onchange="changeAccentColor()"', html)
        for viejo in ('Configuración del Administrador', 'Nombre del Administrador', 'Guardar Configuración', 'max-width: 720px',
                      'Defecto)', 'Azul Océano', 'Verde Menta'):
            with self.subTest(viejo=viejo):
                self.assertNotIn(viejo, html)
