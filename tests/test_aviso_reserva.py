"""Aviso al reservar una clase (21-nov): alumno y profesor, con campanita y correo con diseno. Datos ficticios.

Los avisos salen solo despues de guardar (on_commit). Privacidad: cada uno ve el nombre y apellido del otro y nada
mas (ni RUT, ni correo, ni telefono). El apoderado de un menor esta en test_apoderados_reservas.py.
"""

from unittest import mock

import re

from django.conf import settings
from django.core import mail
from django.urls import reverse

from alumnos.exceptions import SinClasesDisponiblesError
from alumnos.services import InscripcionService
from notificaciones.models import Notificacion
from tests.test_cancelar_4_horas import EN_5_HORAS
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, RUT_PROFE, Escenario, dar_paquete


class AvisoDeReservaTests(Escenario):

    def setUp(self):
        for persona, apellido in ((self.ana, 'Soto'), (self.profe, 'Rojas')):
            persona.user.last_name = apellido
            persona.user.save()
        self.ana.user.email, self.ana.user.telefono = 'ana@lbwus.cl', '922222222'  # que existan: si no, la prueba de
        self.ana.user.save()  # privacidad no buscaria nada
        dar_paquete(self.ana, self.profe)

    def reservar(self, alumno=None):
        with self.captureOnCommitCallbacks(execute=True):
            return InscripcionService.inscribir_alumno_en_sesion(
                alumno or self.ana, crear_sesion(self.clase, dias=EN_5_HORAS).pk)

    def correo_a(self, user):
        [correo] = [m for m in mail.outbox if m.to == [user.email]]
        return correo

    def test_la_alumna_recibe_campanita_y_correo_con_boton(self):
        inscripcion = self.reservar()
        [aviso] = Notificacion.objects.filter(usuario=self.ana.user)
        self.assertIn('Tu clase (Algebra) con Profe Rojas quedó reservada para el', aviso.texto)
        correo = self.correo_a(self.ana.user)
        html = correo.alternatives[0][0]
        ruta = reverse('detalle_clase', args=[inscripcion.pk])
        enlace = f'{settings.SITIO_URL}{ruta}'
        self.assertEqual(correo.subject, 'Clase reservada - LBWUS')
        self.assertIn(aviso.texto, correo.body)  # el texto sirve sin el diseno
        self.assertIn(aviso.texto, html)
        self.assertIn(f'href="{enlace}"', html)  # el boton lleva a la pagina de la clase, con enlace completo
        self.assertIn(enlace, correo.body)
        self.assertEqual(aviso.enlace, ruta)  # y la campanita, al mismo lugar

    def test_el_boton_del_correo_abre_la_pagina_de_la_clase_de_cada_uno(self):
        inscripcion = self.reservar()
        for persona, rut in ((self.ana, RUT_ANA), (self.profe, RUT_PROFE)):
            html = self.correo_a(persona.user).alternatives[0][0]
            [ruta] = re.findall(rf'href="{re.escape(settings.SITIO_URL)}(/[^"]+)"', html)
            with self.subTest(persona=persona.user.first_name):
                self.assertEqual(ruta, reverse('detalle_clase', args=[inscripcion.pk]))
                self.entrar(rut)
                self.assertEqual(self.client.get(ruta).status_code, 200)

    def test_el_profesor_ve_nombre_y_apellido_de_la_alumna(self):
        self.reservar()
        correo = self.correo_a(self.profe.user)
        self.assertIn('Ana Soto reservó Algebra para el', correo.body)
        self.assertIn('Ana Soto reservó Algebra para el', correo.alternatives[0][0])

    def test_nadie_recibe_rut_correo_ni_telefono_del_otro(self):
        self.reservar()
        privados = {
            self.ana.user: [self.profe.user.rut, self.profe.user.email, self.profe.user.telefono],
            self.profe.user: [self.ana.user.rut, self.ana.user.email, self.ana.user.telefono],
        }
        for destinatario, ajenos in privados.items():
            correo = self.correo_a(destinatario)
            for dato in ajenos:
                with self.subTest(destinatario=destinatario.first_name, dato=dato):
                    self.assertTrue(dato)  # el dato existe: si estuviera vacio la prueba no probaria nada
                    self.assertNotIn(dato, correo.body)
                    self.assertNotIn(dato, correo.alternatives[0][0])

    def test_un_nombre_con_html_no_se_vuelve_html(self):
        self.profe.user.last_name = '<b>Rojas</b>'
        self.profe.user.save()
        self.reservar()
        html = self.correo_a(self.ana.user).alternatives[0][0]
        self.assertIn('&lt;b&gt;Rojas&lt;/b&gt;', html)
        self.assertNotIn('<b>Rojas', html)

    def test_si_el_correo_falla_la_reserva_y_la_campanita_siguen(self):
        with mock.patch('alumnos.correo.send_mail', side_effect=OSError('sin servidor')), \
                self.assertLogs('alumnos.correo', 'ERROR'):
            inscripcion = self.reservar()
        self.assertTrue(inscripcion.pk)
        self.assertTrue(Notificacion.objects.filter(usuario=self.ana.user).exists())
        self.assertEqual(mail.outbox, [])

    def test_si_la_reserva_falla_no_sale_ningun_aviso(self):
        with self.assertRaises(SinClasesDisponiblesError):  # Beto no tiene paquete
            self.reservar(self.beto)
        self.assertEqual((Notificacion.objects.count(), mail.outbox), (0, []))
