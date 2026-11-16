"""Panel docente, etapa 3 del rediseno: Perfil (foto), Saldo (cobro, tablas), Buzon (ventana de privacidad) y Agenda.

Cada pantalla conserva sus datos y sus ids (los scripts y las pruebas de pagos dependen de ellos): solo cambia el marcado de diseno.
"""

import re
from unittest import mock

from django.urls import reverse

from alumnos import liquidacion
from tests.test_cuenta_bancaria import CUENTA
from tests.test_paquetes import RUT_PROFE, Escenario


def _seccion(html, nombre):
    inicio = html.index(f'id="sec-{nombre}"')
    siguiente = html.find('<section', inicio + 1)
    return html[inicio:siguiente if siguiente != -1 else len(html)]


class PanelDeCuentaTests(Escenario):

    def panel(self):
        self.entrar(RUT_PROFE)
        return self.client.get(reverse('panel_profesor')).content.decode()

    # --- Perfil ---

    def test_la_foto_usa_la_estructura_del_diseno_y_no_estilos_en_linea(self):
        perfil = _seccion(self.panel(), 'perfil')
        for pieza in ('class="prof-foto"', 'id="prof-foto-preview"', 'class="prof-foto-input"', 'class="prof-foto-boton"',
                      'id="prof-foto-texto-boton"', 'Elegir foto', 'bi-person'):
            self.assertIn(pieza, perfil)
        self.assertNotIn('width: 120px', perfil)
        # el campo sigue llamandose igual para el servidor y acepta solo imagenes
        self.assertRegex(perfil, r'<input type="file" id="prof-foto" name="foto_perfil"[^>]*accept="image/jpeg,image/png,image/webp"')

    def test_rut_y_direccion_se_marcan_como_privados_y_los_datos_siguen_viniendo_del_servidor(self):
        perfil = _seccion(self.panel(), 'perfil')
        self.assertEqual(perfil.count('class="prof-privado"'), 2)
        self.assertIn('Solo tú lo ves', perfil)
        self.assertIn(f'value="{RUT_PROFE}"', perfil)

    # --- Saldo ---

    def test_sin_cuenta_el_cobro_avisa_arriba_y_no_ofrece_el_retiro(self):
        saldo = _seccion(self.panel(), 'saldo')
        self.assertIn('class="prof-card prof-pagos"', saldo)
        self.assertEqual(len(re.findall(r'<li><i class="bi ', saldo[saldo.index('prof-pagos-reglas'):])), 3)
        self.assertEqual(saldo.count('prof-aviso--warn'), 1)
        self.assertIn('Registra tu cuenta bancaria para poder solicitar retiros', saldo)
        self.assertLess(saldo.index('prof-aviso--warn'), saldo.index('id="formCuentaBancaria"'))  # el aviso va antes de los formularios
        self.assertNotIn('formSolicitarRetiro', saldo)
        self.assertNotIn('cuenta_password', saldo)  # la contraseña solo se pide para CAMBIAR una cuenta

    def test_los_formularios_de_pago_conservan_sus_ids_y_acciones(self):
        saldo = _seccion(self.panel(), 'saldo')
        for pieza in ('id="formCuentaBancaria"', 'id="formFrecuenciaPago"', 'onsubmit="submitFormJson(event)"',
                      'id="cuenta_banco"', 'id="cuenta_tipo"', 'id="cuenta_numero"', 'id="frecuencia_pago"',
                      f'action="{reverse("guardar_cuenta_bancaria")}"', f'action="{reverse("guardar_frecuencia_pago")}"'):
            self.assertIn(pieza, saldo)
        self.assertEqual(saldo.count('class="prof-pago-form"'), 2)

    def test_con_cuenta_y_saldo_bajo_el_minimo_explica_que_se_acumula(self):
        self.entrar(RUT_PROFE)
        self.client.post(reverse('guardar_cuenta_bancaria'), CUENTA)
        saldo = _seccion(self.client.get(reverse('panel_profesor')).content.decode(), 'saldo')
        self.assertIn('se acumula hasta llegar al mínimo', saldo)
        self.assertNotIn('Registra tu cuenta bancaria', saldo)
        self.assertNotIn('formSolicitarRetiro', saldo)
        self.assertIn('id="cuenta_password"', saldo)  # cambiar una cuenta existente pide la contraseña

    def test_con_cuenta_y_saldo_suficiente_aparece_el_retiro_al_final_y_sin_avisos(self):
        self.entrar(RUT_PROFE)
        self.client.post(reverse('guardar_cuenta_bancaria'), CUENTA)
        with mock.patch.object(liquidacion, 'MINIMO', 0):  # el saldo (0) alcanza el minimo: no se inventan pagos
            saldo = _seccion(self.client.get(reverse('panel_profesor')).content.decode(), 'saldo')
        self.assertIn('id="formSolicitarRetiro"', saldo)
        self.assertIn('onsubmit="submitRetiroForm(event)"', saldo)
        self.assertIn('prof-form-btn prof-form-btn-accent prof-btn-auto', saldo)
        self.assertNotIn('prof-aviso--warn', saldo)
        self.assertLess(saldo.index('id="formFrecuenciaPago"'), saldo.index('id="formSolicitarRetiro"'))  # cuenta, frecuencia y al final el retiro

    def test_las_dos_tablas_usan_el_diseno_con_su_estado_vacio_y_sin_la_etiqueta_interna(self):
        saldo = _seccion(self.panel(), 'saldo')
        self.assertEqual(saldo.count('class="prof-table-wrapper"'), 2)
        self.assertEqual(saldo.count('class="prof-table"'), 2)
        self.assertEqual(saldo.count('prof-tabla-vacia'), 2)
        self.assertNotIn('Regla S4-09', saldo)
        self.assertNotIn('border-collapse: collapse', saldo)  # el estilo en linea de las tablas ya no esta
        self.assertIn('Detalle de liquidaciones', saldo)

    # --- Buzon y Agenda ---

    def test_el_buzon_abre_la_ventana_de_privacidad_desde_el_encabezado(self):
        buzon = _seccion(self.panel(), 'buzon')
        self.assertIn('prof-section-header prof-header-con-accion', buzon)
        self.assertIn('class="btn-ayuda-mensajes"', buzon)
        self.assertEqual(buzon.count('id="dialogo-mensajes"'), 1)
        self.assertIn('Buzón de alumnos', buzon)

    def test_agenda_y_observaciones_usan_los_titulos_del_diseno(self):
        html = self.panel()
        self.assertIn('Mi agenda', _seccion(html, 'agenda'))
        self.assertIn('Observaciones de clases realizadas', _seccion(html, 'agenda'))

    # --- Hojas ---

    def test_la_capa_carga_formularios_agenda_y_cuenta_en_su_orden(self):
        html = self.panel()
        orden = [f'panel/06{x}_pulido_docente_{n}.css' for x, n in
                 (('a', 'marco'), ('b', 'inicio'), ('c', 'formularios'), ('d', 'tablas'), ('e', 'agenda'), ('f', 'cuenta'), ('h', 'cierre'))]
        posiciones = [html.index(hoja) for hoja in orden]
        self.assertEqual(posiciones, sorted(posiciones))
