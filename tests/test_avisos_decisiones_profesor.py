"""Avisos al profesor cuando soporte decide su titulo o una especializacion (fase 5, decidido 07-nov).

Campanita + correo, solo despues de confirmar la decision (on_commit). El motivo de un rechazo no va ni en la
campanita ni en el correo: se lee solo en el panel. Datos ficticios.
"""

from unittest import mock

from django.core import mail
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Especialidad, Profesor
from notificaciones.models import Notificacion
from soporte.models import Ticket
from tests.test_apoderados import crear_agente
from tests.test_especialidad import crear_profesor
from tests.test_especializaciones_revision import pdf
from user_profesor import especializaciones, titulo

MOTIVO = 'El documento est\u00e1 borroso: no se lee el RUT 12.345.678-5.'


class AvisosDecisionesTests(TestCase):

    def setUp(self):
        crear_agente('10000001-9', Ticket.TITULOS)
        crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        self.profesor = crear_profesor('22222222-2', 'profe@lbwus.cl', Especialidad.objects.create(nombre='Mate'),
                                       titulo_estado=Profesor.TITULO_PENDIENTE)
        titulo.subir(self.profesor, pdf('t.pdf'))  # en revision, como cuando soporte lo decide
        self.algebra, self.calculo = (Asignatura.objects.create(nombre=n) for n in ('\u00c1lgebra', 'C\u00e1lculo'))
        self.esp = especializaciones.subir(self.profesor, 'Diplomado en \u00c1lgebra', pdf('d.pdf'), [self.algebra.pk])
        mail.outbox.clear()

    def decidir(self, funcion, *args, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            return funcion(*args, **kwargs)

    def campanita(self):
        return list(Notificacion.objects.filter(usuario=self.profesor.user).values('texto', 'enlace'))

    def test_titulo_aprobado_avisa_y_nombra_las_asignaturas_nuevas(self):
        self.decidir(titulo.resolver, self.profesor, True, ids_asignaturas=[self.algebra.pk, self.calculo.pk])
        [aviso] = self.campanita()
        self.assertEqual(aviso['texto'], 'Tu t\u00edtulo profesional fue aprobado. Ya puedes hacer clases. '
                                         'Asignaturas nuevas: \u00c1lgebra, C\u00e1lculo.')
        self.assertEqual(aviso['enlace'], reverse('panel_profesor'))
        [correo] = mail.outbox
        self.assertEqual((correo.subject, correo.to),
                         ('Tu t\u00edtulo fue revisado - LBWUS', [self.profesor.user.email]))
        self.assertIn(aviso['texto'], correo.body)

    def test_titulo_aprobado_sin_asignaturas_no_menciona_ninguna(self):
        self.decidir(titulo.resolver, self.profesor, True)
        self.assertNotIn('Asignaturas nuevas', self.campanita()[0]['texto'])

    def test_titulo_rechazado_no_filtra_el_motivo(self):
        self.decidir(titulo.resolver, self.profesor, False, MOTIVO)
        [aviso] = self.campanita()
        self.assertEqual(aviso['texto'], 'Tu t\u00edtulo profesional fue rechazado. '
                                         'Revisa el motivo en tu panel y vuelve a subirlo.')
        self.assertNotIn('borroso', aviso['texto'] + mail.outbox[0].body)
        self.assertNotIn('12.345.678-5', aviso['texto'] + mail.outbox[0].body)

    def test_especializacion_aprobada_nombra_lo_que_quedo_dictando(self):
        self.decidir(especializaciones.resolver, self.esp, True, ids_asignaturas=[self.calculo.pk])
        [aviso] = self.campanita()
        self.assertEqual(aviso['texto'], 'Tu especializaci\u00f3n \u00abDiplomado en \u00c1lgebra\u00bb fue aprobada. '
                                         'Asignaturas nuevas: C\u00e1lculo.')
        [correo] = mail.outbox
        self.assertEqual((correo.subject, correo.to), ('Tu especializaci\u00f3n fue revisada - LBWUS',
                                                       [self.profesor.user.email]))

    def test_especializacion_rechazada_no_filtra_el_motivo(self):
        self.decidir(especializaciones.resolver, self.esp, False, MOTIVO)
        [aviso] = self.campanita()
        self.assertEqual(aviso['texto'], 'Tu especializaci\u00f3n \u00abDiplomado en \u00c1lgebra\u00bb fue rechazada. '
                                         'Revisa el motivo en tu panel.')
        self.assertNotIn('borroso', aviso['texto'] + mail.outbox[0].body)
        self.assertNotIn('12.345.678-5', aviso['texto'] + mail.outbox[0].body)

    def test_si_la_decision_falla_no_sale_ningun_aviso(self):
        with self.assertRaises(Exception):
            self.decidir(especializaciones.resolver, self.esp, False, '')  # sin motivo
        with self.assertRaises(Exception):
            self.decidir(especializaciones.resolver, self.esp, True)  # sin asignaturas
        with self.assertRaises(Exception):
            self.decidir(titulo.resolver, self.profesor, False, '')  # sin motivo
        self.assertEqual((self.campanita(), mail.outbox), ([], []))

    def test_si_se_deshace_la_decision_despues_de_avisar_no_sale_nada(self):
        # El aviso se registra antes de cerrar el ticket: si eso falla, todo se deshace y no se avisa.
        with mock.patch('user_profesor.especializaciones.cerrar_tickets', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self.decidir(especializaciones.resolver, self.esp, False, MOTIVO)
        self.assertEqual((self.campanita(), mail.outbox), ([], []))
        self.esp.refresh_from_db()
        self.assertEqual(self.esp.estado, 'en_revision')

    def test_si_se_deshace_la_decision_del_titulo_no_sale_ningun_correo(self):
        with self.assertRaises(RuntimeError):
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():  # la transaccion que contiene la decision se deshace
                    titulo.resolver(self.profesor, True)
                    raise RuntimeError('boom')
        self.assertEqual((self.campanita(), mail.outbox), ([], []))

    def test_no_avisa_dos_veces_si_otro_agente_ya_decidio(self):
        self.decidir(especializaciones.resolver, self.esp, False, MOTIVO)
        with self.assertRaises(Exception):
            self.decidir(especializaciones.resolver, self.esp, True, ids_asignaturas=[self.algebra.pk])
        self.assertEqual(len(self.campanita()), 1)
        self.assertEqual(len(mail.outbox), 1)
