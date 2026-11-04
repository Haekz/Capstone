"""Eliminar la cuenta de profesores y apoderados (paso 5 de la respuesta legal del 02-nov): que bloquea, que se
conserva, que datos propios se quitan y que el historial de otras personas no se toca. Datos ficticios."""

import tempfile
from datetime import time
from unittest import mock

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import override_settings
from django.utils import timezone

from agenda.models import HorarioSemanal
from alumnos import catalogos
from alumnos.models import Alumno, Clase, CuentaBancaria, CustomUser, Inscripcion, Profesor, SolicitudRetiro
from apoderados.models import Apoderado, CompraApoderado, Documento, Invitacion, SolicitudAdolescente, Vinculo
from soporte.models import Ticket
from supresiones import evaluacion, registro, solicitud
from tests.test_apoderados import RUT, crear_agente, crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado, hace_anios
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete

RUT_MENOR = '77777777-7'
RUT_OTRO_APODERADO, RUT_OTRO_MENOR = '99999999-9', '55555555-5'


def nombres(ev):
    return [c.nombre for c in ev.categorias]


def con_datos_propios(profesor):
    """El profesor tal como esta en produccion: titulo, cuenta bancaria y horario cargados."""
    Profesor.objects.filter(pk=profesor.pk).update(
        titulo_contenido=b'cifrado', titulo_formato='PDF', titulo_observacion='Falta firma',
        titulo_estado=Profesor.TITULO_APROBADO)
    cuenta = CuentaBancaria(profesor=profesor, banco=list(catalogos.BANCOS)[0], tipo_cuenta='rut_vista')
    cuenta.asignar_numero('123456789')
    cuenta.save()
    HorarioSemanal.objects.create(profesor=profesor, dia_semana=0, hora_inicio=time(9), hora_fin=time(10))


class EvaluacionDelProfesorTests(Escenario):

    def test_sin_pendientes_se_puede_y_dice_que_se_quita(self):
        ev = evaluacion.evaluar(self.otro.user)
        self.assertTrue(ev.puede)
        self.assertEqual(nombres(ev), ['Datos de la cuenta', 'Título profesional', 'Cuenta bancaria y horario'])
        self.assertFalse(ev.conserva_algo)

    def test_una_clase_por_dictar_impide(self):
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, 3),
                                   paquete=dar_paquete(self.ana, self.profe))
        ev = evaluacion.evaluar(self.profe.user)
        self.assertFalse(ev.puede)
        self.assertTrue(any('por dictar' in b for b in ev.bloqueos))

    def test_clases_pagadas_sin_usar_por_alumnos_con_el_impiden(self):
        dar_paquete(self.ana, self.profe)
        ev = evaluacion.evaluar(self.profe.user)
        self.assertTrue(any('sin usar por alumnos' in b for b in ev.bloqueos))

    def test_el_dinero_disponible_para_retirar_impide(self):
        with mock.patch('user_profesor.views.calcular_saldos', return_value={'disponible': 12000}):
            ev = evaluacion.evaluar(self.otro.user)
        self.assertFalse(ev.puede)
        self.assertIn('$12.000', ev.bloqueos[0])

    def test_un_retiro_en_tramite_impide(self):
        SolicitudRetiro.objects.create(profesor=self.otro, monto=5000, estado=SolicitudRetiro.APROBADO)
        ev = evaluacion.evaluar(self.otro.user)
        self.assertTrue(any('retiro(s) de dinero en trámite' in b for b in ev.bloqueos))

    def test_un_retiro_ya_pagado_no_impide_pero_se_conserva(self):
        SolicitudRetiro.objects.create(profesor=self.otro, monto=5000, estado=SolicitudRetiro.PAGADO)
        ev = evaluacion.evaluar(self.otro.user)
        self.assertTrue(ev.puede)
        self.assertIn('Clases, pagos y retiros', nombres(ev))
        self.assertIn('Tickets de soporte', nombres(ev))


class EliminarProfesorTests(Escenario):

    def test_sin_historial_se_borra_por_completo_y_no_toca_a_los_alumnos(self):
        self.assertTrue(registro.eliminar(self.otro.user))
        self.assertFalse(CustomUser.objects.filter(pk=self.otro.user_id).exists())
        self.assertFalse(Clase.objects.filter(pk=self.clase_otro.pk).exists())
        self.assertTrue(Alumno.objects.filter(pk=self.ana.pk).exists())

    def test_con_historial_se_seudonimiza_y_conserva_las_clases_de_los_alumnos(self):
        con_datos_propios(self.profe)
        paquete = dar_paquete(self.ana, self.profe, plan='flexible')
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, -3), paquete=paquete)
        SolicitudRetiro.objects.create(profesor=self.profe, monto=5000, estado=SolicitudRetiro.PAGADO)
        sin_reservas = crear_sesion(self.clase, 5)

        self.assertFalse(registro.eliminar(self.profe.user))

        user = CustomUser.objects.get(pk=self.profe.user_id)
        self.assertEqual((user.first_name, user.email, user.rut), ('Cuenta eliminada', '', None))
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.suprimida)
        self.assertEqual(Inscripcion.objects.filter(alumno=self.ana).count(), 1)  # el historial de Ana sigue
        self.assertEqual(SolicitudRetiro.objects.filter(profesor=self.profe).count(), 1)
        sin_reservas.refresh_from_db()
        self.assertEqual(sin_reservas.estado, 'cancelada')

    def test_con_historial_se_quitan_titulo_cuenta_bancaria_y_horario_y_sale_del_catalogo(self):
        con_datos_propios(self.profe)
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, -3),
                                   paquete=dar_paquete(self.ana, self.profe, plan='flexible'))
        self.assertIn(self.profe, Profesor.objects.habilitados())

        registro.eliminar(self.profe.user)

        profesor = Profesor.objects.get(pk=self.profe.pk)
        self.assertEqual((profesor.titulo_contenido, profesor.titulo_formato, profesor.titulo_observacion), (None, '', ''))
        self.assertEqual(profesor.titulo_estado, Profesor.TITULO_PENDIENTE)
        self.assertFalse(CuentaBancaria.objects.filter(profesor=profesor).exists())
        self.assertFalse(HorarioSemanal.objects.filter(profesor=profesor).exists())
        self.assertNotIn(profesor, Profesor.objects.habilitados())
        self.assertNotIn(self.clase, Clase.objects.habilitadas())

    def test_la_solicitud_del_usuario_tambien_lo_elimina(self):
        agente = crear_agente('10000001-9', Ticket.PRIVACIDAD)
        sol, _ = solicitud.abrir(self.otro.user)
        solicitud.ejecutar(sol, agente)
        self.assertFalse(CustomUser.objects.filter(pk=self.otro.user_id).exists())


class EvaluacionDelApoderadoTests(Escenario):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR)
        self.menor = self.vinculo.alumno

    def test_ser_apoderado_verificado_de_un_menor_impide_hasta_desvincularse(self):
        ev = evaluacion.evaluar(self.apoderado.user)
        self.assertFalse(ev.puede)
        self.assertIn('1 estudiante(s) menor(es)', ev.bloqueos[0])
        self.vinculo.revocar(self.apoderado.user)
        self.assertTrue(evaluacion.evaluar(self.apoderado.user).puede)

    def test_un_estudiante_que_ya_cumplio_18_no_impide(self):
        CustomUser.objects.filter(pk=self.menor.user_id).update(fecha_nacimiento=hace_anios(20))
        self.assertTrue(evaluacion.evaluar(self.apoderado.user).puede)

    def test_un_vinculo_pendiente_no_impide(self):
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.PENDIENTE)
        self.assertTrue(evaluacion.evaluar(self.apoderado.user).puede)

    def test_dice_que_se_quita_y_que_se_conserva(self):
        self.vinculo.revocar(self.apoderado.user)
        ev = evaluacion.evaluar(self.apoderado.user)
        self.assertEqual(nombres(ev)[:2], ['Datos de la cuenta', 'Documentos de identidad'])
        self.assertIn('Compras y vínculos', nombres(ev))
        self.assertIn('Tickets de soporte', nombres(ev))


class EliminarApoderadoTests(Escenario):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR, estado=Vinculo.PENDIENTE)
        self.menor = self.vinculo.alumno

    def invitar(self, correo='mama@demo.cl'):
        solicitud = SolicitudAdolescente.objects.create(alumno=self.menor, correo_apoderado=correo, version_declaracion='1',
                                                        declaracion_aceptada=timezone.now())
        invitacion = solicitud.invitar(correo)
        invitacion.vinculo = self.vinculo
        invitacion.save()

    def subir_documentos(self):
        Documento.objects.create(apoderado=self.apoderado, tipo=Documento.CARNET_FRENTE, formato='JPEG', contenido=b'x')
        Documento.objects.create(vinculo=self.vinculo, tipo=Documento.CERTIFICADO, formato='PDF', contenido=b'x')

    def test_sin_historial_se_borra_y_el_estudiante_sigue(self):
        self.subir_documentos()
        self.assertTrue(registro.eliminar(self.apoderado.user))
        self.assertFalse(CustomUser.objects.filter(pk=self.apoderado.user_id).exists())
        self.assertFalse(Documento.objects.exists())
        self.assertTrue(Alumno.objects.filter(pk=self.menor.pk).exists())

    def test_al_borrarlo_su_correo_ya_no_queda_en_las_invitaciones_del_estudiante(self):
        self.invitar()
        self.assertTrue(registro.eliminar(self.apoderado.user))
        self.assertEqual(Invitacion.objects.get().correo, '')
        self.assertEqual(SolicitudAdolescente.objects.get().correo_apoderado, '')

    def test_con_un_vinculo_que_fue_verificado_se_seudonimiza_y_se_conserva_el_registro(self):
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.VERIFICADO)
        self.vinculo.refresh_from_db()
        self.vinculo.revocar(self.apoderado.user)
        self.subir_documentos()
        self.invitar()

        self.assertFalse(registro.eliminar(self.apoderado.user))

        user = CustomUser.objects.get(pk=self.apoderado.user_id)
        self.assertEqual((user.first_name, user.email, user.rut), ('Cuenta eliminada', '', None))
        self.assertFalse(user.is_active)
        self.assertTrue(Vinculo.objects.filter(pk=self.vinculo.pk, estado=Vinculo.REVOCADO).exists())
        self.assertFalse(Documento.objects.exists())
        self.assertEqual(Invitacion.objects.get().correo, '')
        self.assertEqual(SolicitudAdolescente.objects.get().correo_apoderado, '')
        self.assertTrue(Alumno.objects.filter(pk=self.menor.pk).exists())

    def test_una_compra_pagada_se_conserva(self):
        compra = CompraApoderado.objects.create(paquete=dar_paquete(self.menor, self.profe), apoderado=self.apoderado,
                                                vinculo=self.vinculo)
        self.assertFalse(registro.eliminar(self.apoderado.user))
        compra.refresh_from_db()
        self.assertEqual(compra.apoderado_id, self.apoderado.pk)


class AllauthYArchivosTests(Escenario):
    """Huecos que la cascada no cierra: el correo en allauth y los archivos del disco."""

    def conectar_google(self, user):
        EmailAddress.objects.create(user=user, email='ana.google@demo.cl', verified=True, primary=True)
        SocialAccount.objects.create(user=user, provider='google', uid='1234', extra_data={'email': 'ana.google@demo.cl'})

    def test_al_seudonimizar_no_queda_el_correo_ni_la_cuenta_de_google(self):
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, -3),
                                   paquete=dar_paquete(self.ana, self.profe, plan='flexible'))
        self.conectar_google(self.ana.user)
        self.assertFalse(registro.eliminar(self.ana.user))
        self.assertFalse(EmailAddress.objects.exists())
        self.assertFalse(SocialAccount.objects.exists())

    def test_al_borrar_por_completo_tambien_se_borra_la_foto_del_disco(self):
        with tempfile.TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            user = self.beto.user
            user.foto_perfil.save('foto.png', ContentFile(b'imagen'), save=True)
            nombre = user.foto_perfil.name
            self.assertTrue(default_storage.exists(nombre))
            self.assertTrue(registro.eliminar(user))
            self.assertFalse(default_storage.exists(nombre))

    def test_al_seudonimizar_tambien_se_borra_la_foto_del_disco(self):
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, -3),
                                   paquete=dar_paquete(self.ana, self.profe, plan='flexible'))
        with tempfile.TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            user = self.ana.user
            user.foto_perfil.save('foto.png', ContentFile(b'imagen'), save=True)
            nombre = user.foto_perfil.name
            self.assertFalse(registro.eliminar(user))
            self.assertFalse(default_storage.exists(nombre))
