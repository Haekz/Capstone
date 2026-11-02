"""El profesor cancela una clase reservada (paso A3b, decidido 02-nov). Datos ficticios."""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from agenda import cancelacion
from alumnos.exceptions import InscripcionError
from alumnos.models import Inscripcion, SesionClase
from alumnos.services import InscripcionService
from apoderados.models import Apoderado, Vinculo
from notificaciones.models import Notificacion
from tests.test_apoderados import RUT, crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, RUT_PROFE, Escenario, dar_paquete

EN_13_HORAS, EN_11_HORAS = 13 / 24, 11 / 24
RUT_MENOR = '77777777-7'  # distinto de los del Escenario
MENSAJE_12H = 'Solo puedes cancelar con 12 horas'


class ProfesorCancelaTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)

    def reservar(self, dias=EN_13_HORAS, alumno=None, **extra):
        sesion = crear_sesion(self.clase, dias=dias, cupo=1)
        return InscripcionService.inscribir_alumno_en_sesion(alumno or self.ana, sesion.pk, **extra)

    def cancelar(self, inscripcion, profesor=None):
        with self.captureOnCommitCallbacks(execute=True):
            return cancelacion.cancelar(profesor or self.profe, inscripcion.pk)

    def test_con_13_horas_se_puede_y_la_clase_vuelve_al_paquete(self):
        inscripcion = self.reservar()
        paquete = inscripcion.paquete
        self.assertEqual(paquete.clases_usadas, 1)
        self.cancelar(inscripcion)
        inscripcion.refresh_from_db()
        paquete.refresh_from_db()
        self.assertEqual((inscripcion.estado, paquete.clases_usadas), (Inscripcion.ESTADO_CANCELADA, 0))

    def test_con_11_horas_no_se_puede(self):
        inscripcion = self.reservar(EN_11_HORAS)
        with self.assertRaisesMessage(InscripcionError, MENSAJE_12H):
            self.cancelar(inscripcion)
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_el_limite_son_exactamente_12_horas(self):
        inscripcion = self.reservar(13 / 24)
        inicio = inscripcion.sesion.fecha_hora_inicio
        with mock.patch('django.utils.timezone.now', return_value=inicio - timedelta(hours=12)):
            self.assertTrue(cancelacion.a_tiempo(inscripcion.sesion))
        with mock.patch('django.utils.timezone.now', return_value=inicio - timedelta(hours=12, seconds=-1)):
            self.assertFalse(cancelacion.a_tiempo(inscripcion.sesion))

    def test_la_cancelacion_del_profesor_no_se_paga(self):
        inscripcion = self.reservar()
        self.cancelar(inscripcion)
        self.assertFalse(Inscripcion.objects.pagables().filter(pk=inscripcion.pk).exists())

    def test_se_cierra_esa_hora_en_todas_las_asignaturas(self):
        from datetime import time
        from alumnos.models import Asignatura, Clase
        calculo = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Calculo'),
                                       modalidad='online', horario=time(10), profesor=self.profe)
        inscripcion = self.reservar()
        hermano = crear_sesion(calculo, dias=EN_13_HORAS, cupo=1)
        otra_hora = crear_sesion(self.clase, dias=EN_13_HORAS + 1, cupo=1)
        self.cancelar(inscripcion)
        inscripcion.sesion.refresh_from_db()
        hermano.refresh_from_db()
        otra_hora.refresh_from_db()
        self.assertEqual((inscripcion.sesion.estado, hermano.estado, otra_hora.estado),
                         (SesionClase.ESTADO_CANCELADA, SesionClase.ESTADO_CANCELADA,
                          SesionClase.ESTADO_PROGRAMADA))
        self.assertNotIn(hermano, SesionClase.objects.disponibles())

    def test_solo_puede_cancelar_sus_propias_clases(self):
        inscripcion = self.reservar()
        with self.assertRaisesMessage(InscripcionError, 'Reserva no encontrada'):
            self.cancelar(inscripcion, profesor=self.otro)
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_no_se_cancela_dos_veces(self):
        inscripcion = self.reservar()
        self.cancelar(inscripcion)
        with self.assertRaises(InscripcionError):
            self.cancelar(inscripcion)

    def test_avisa_al_alumno_adulto_por_campanita_y_correo(self):
        self.cancelar(self.reservar())
        [aviso] = Notificacion.objects.filter(usuario=self.ana.user)
        self.assertIn('Tu profesor canceló la clase de Algebra del', aviso.texto)
        self.assertEqual(aviso.enlace, reverse('alumno_pag1'))
        [correo] = [m for m in mail.outbox if m.to == [self.ana.user.email]]
        self.assertEqual(correo.subject, 'Tu profesor canceló una clase - LBWUS')
        self.assertIn(aviso.texto, correo.body)

    def test_el_aviso_no_lleva_datos_del_profesor(self):
        self.cancelar(self.reservar())
        texto = Notificacion.objects.get(usuario=self.ana.user).texto
        cuerpo = [m for m in mail.outbox if m.to == [self.ana.user.email]][0].body
        for privado in filter(None, (RUT_PROFE, self.profe.user.email, self.profe.user.last_name,
                                     self.profe.user.first_name)):
            self.assertNotIn(privado, texto)
            self.assertNotIn(privado, cuerpo)

    def test_si_es_menor_avisa_al_apoderado_y_no_al_menor(self):
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        vinculo = crear_menor_vinculado(apoderado, rut=RUT_MENOR)
        dar_paquete(vinculo.alumno, self.profe)
        inscripcion = self.reservar(alumno=vinculo.alumno, vinculo=vinculo)
        self.cancelar(inscripcion)
        self.assertFalse(Notificacion.objects.filter(usuario=vinculo.alumno.user).exists())
        [aviso] = Notificacion.objects.filter(usuario=apoderado.user)
        self.assertIn(f'la clase de {vinculo.alumno.user.first_name} de Algebra', aviso.texto)
        self.assertEqual(aviso.enlace, reverse('apoderado_clases_estudiante', args=[vinculo.pk]))
        self.assertEqual([m.to for m in mail.outbox if m.to == [apoderado.user.email]], [[apoderado.user.email]])

    def test_si_la_cancelacion_falla_no_sale_ningun_aviso(self):
        inscripcion = self.reservar(EN_11_HORAS)
        with self.assertRaises(InscripcionError):
            self.cancelar(inscripcion)
        self.assertFalse(Notificacion.objects.filter(usuario=self.ana.user).exists())


class BotonCancelarTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.entrar(RUT_PROFE)

    def reservar(self, dias):
        return InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=dias, cupo=1).pk)

    def cancelar(self, inscripcion):
        return self.client.post(reverse('agenda_cancelar_clase', args=[inscripcion.pk]), follow=True)

    def test_el_boton_aparece_con_12_horas_o_mas_y_se_explica_si_no(self):
        self.reservar(EN_13_HORAS)
        self.reservar(EN_11_HORAS)
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, 'Cancelar clase</button>', count=1)
        self.assertContains(r, 'Faltan menos de 12 h')

    def test_cancelar_desde_el_panel_avisa_y_vuelve(self):
        r = self.cancelar(self.reservar(EN_13_HORAS))
        self.assertRedirects(r, reverse('panel_profesor'))
        self.assertContains(r, 'Clase cancelada')
        self.assertEqual(Inscripcion.objects.get().estado, Inscripcion.ESTADO_CANCELADA)

    def test_con_menos_de_12_horas_muestra_el_motivo_y_no_cancela(self):
        r = self.cancelar(self.reservar(EN_11_HORAS))
        self.assertContains(r, MENSAJE_12H)
        self.assertEqual(Inscripcion.objects.get().estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_un_alumno_no_puede_cancelar_por_el_profesor(self):
        inscripcion = self.reservar(EN_13_HORAS)
        self.entrar(RUT_ANA)
        self.cancelar(inscripcion)
        self.assertEqual(Inscripcion.objects.get().estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_solo_por_post(self):
        inscripcion = self.reservar(EN_13_HORAS)
        self.assertEqual(self.client.get(reverse('agenda_cancelar_clase', args=[inscripcion.pk])).status_code, 405)
