"""Registro de supresiones (respuesta legal, E4): huellas, exportar, y volver a eliminar a quien un respaldo restaurado
trajo de vuelta. Datos ficticios."""

import hashlib
import json
import os
import tempfile
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from alumnos.models import CustomUser, Inscripcion
from soporte.models import Ticket
from supresiones import registro, solicitud
from supresiones.models import RegistroSupresion
from tests.test_apoderados import User, crear_agente, entrar_soporte
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, RUT_BETO, Escenario, dar_paquete
from tests.test_retiros import crear_admin, entrar_admin


def volver_de_un_respaldo(rut, correo, hace_dias=10, **datos):
    """La cuenta tal como la trae un respaldo anterior a la supresion: misma persona, creada antes."""
    user = User.objects.create_user(rut, rut=rut, email=correo, first_name='Persona', **datos)
    User.objects.filter(pk=user.pk).update(date_joined=timezone.now() - timedelta(days=hace_dias))
    return User.objects.get(pk=user.pk)


class HuellaTests(Escenario):

    def test_no_depende_de_como_este_escrito_el_dato(self):
        self.assertEqual(registro.huella('22222222-2'), registro.huella('22.222.222-2'))
        self.assertEqual(registro.huella('12345678-k'), registro.huella('12.345.678-K'))
        self.assertEqual(registro.huella('Ana@Demo.cl '), registro.huella('ana@demo.cl'))

    def test_personas_distintas_dan_huellas_distintas(self):
        self.assertNotEqual(registro.huella('22222222-2'), registro.huella('11111111-1'))

    def test_vacio_no_tiene_huella(self):
        for vacio in ('', None, '   '):
            self.assertEqual(registro.huella(vacio), '')

    def test_no_es_un_hash_simple_depende_de_la_clave(self):
        normal = registro.huella('22222222-2')
        with override_settings(SUPRESIONES_CLAVE='otra-clave'):
            self.assertNotEqual(registro.huella('22222222-2'), normal)
        self.assertNotEqual(normal, hashlib.sha256(b'22222222-2').hexdigest())  # no se adivina probando RUT

    def test_con_una_clave_propia_la_huella_no_depende_de_secret_key(self):
        with override_settings(SUPRESIONES_CLAVE='clave-propia', SECRET_KEY='una'):
            a = registro.huella('22222222-2')
        with override_settings(SUPRESIONES_CLAVE='clave-propia', SECRET_KEY='otra'):
            self.assertEqual(registro.huella('22222222-2'), a)


class EliminarTests(Escenario):

    def test_eliminar_borra_y_anota_solo_huellas(self):
        correo = self.beto.user.email
        self.assertTrue(registro.eliminar(self.beto.user))
        self.assertFalse(CustomUser.objects.filter(pk=self.beto.user_id).exists())
        fila = RegistroSupresion.objects.get()
        self.assertEqual((fila.huella_rut, fila.huella_correo), (registro.huella(RUT_BETO), registro.huella(correo)))
        guardado = str(list(RegistroSupresion.objects.values()))
        self.assertNotIn(RUT_BETO, guardado)
        self.assertNotIn(correo, guardado)
        self.assertNotIn('22222222', guardado)

    def test_una_cuenta_que_se_seudonimiza_tambien_se_anota(self):
        paquete = dar_paquete(self.ana, self.profe, plan='flexible')
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, -3), paquete=paquete)
        self.assertFalse(registro.eliminar(self.ana.user))
        self.assertEqual(RegistroSupresion.objects.get().huella_rut, registro.huella(RUT_ANA))

    def test_una_cuenta_sin_rut_ni_correo_no_deja_una_fila_vacia(self):
        user = User.objects.create_user('sinnada', password='x')
        registro.eliminar(user)
        self.assertFalse(RegistroSupresion.objects.exists())

    def test_la_solicitud_del_usuario_queda_en_el_registro(self):
        crear_agente('10000001-9', Ticket.PRIVACIDAD)
        sol, _ = solicitud.abrir(self.beto.user)
        agente = sol.ticket.asignado
        solicitud.ejecutar(sol, agente)
        self.assertEqual(RegistroSupresion.objects.get().huella_rut, registro.huella(RUT_BETO))

    def test_el_borrado_del_admin_queda_en_el_registro(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        self.client.post(reverse('alumnos_del', args=[self.beto.id_alumno]))
        self.assertFalse(CustomUser.objects.filter(pk=self.beto.user_id).exists())
        self.assertEqual(RegistroSupresion.objects.get().huella_rut, registro.huella(RUT_BETO))


class ReaplicarTests(Escenario):

    def eliminar_a_beto(self):
        correo = self.beto.user.email
        registro.eliminar(self.beto.user)
        return correo

    def test_un_respaldo_que_trae_de_vuelta_la_cuenta_se_elimina_otra_vez(self):
        correo = self.eliminar_a_beto()
        vuelta = volver_de_un_respaldo(RUT_BETO, correo)
        self.assertEqual(registro.reaplicar(), 1)
        self.assertFalse(CustomUser.objects.filter(pk=vuelta.pk).exists())

    def test_simular_solo_cuenta(self):
        correo = self.eliminar_a_beto()
        vuelta = volver_de_un_respaldo(RUT_BETO, correo)
        self.assertEqual(registro.reaplicar(simular=True), 1)
        self.assertTrue(CustomUser.objects.filter(pk=vuelta.pk).exists())

    def test_reconoce_a_la_persona_solo_por_el_correo_si_cambio_de_rut(self):
        correo = self.eliminar_a_beto()
        vuelta = volver_de_un_respaldo('99999999-9', correo)
        self.assertEqual(registro.reaplicar(), 1)
        self.assertFalse(CustomUser.objects.filter(pk=vuelta.pk).exists())

    def test_reconoce_a_la_persona_solo_por_el_rut_si_cambio_de_correo(self):
        self.eliminar_a_beto()
        vuelta = volver_de_un_respaldo(RUT_BETO, 'otro@demo.cl')
        self.assertEqual(registro.reaplicar(), 1)
        self.assertFalse(CustomUser.objects.filter(pk=vuelta.pk).exists())

    def test_quien_se_registro_de_nuevo_despues_de_eliminarse_no_se_toca(self):
        correo = self.eliminar_a_beto()
        nueva = User.objects.create_user(RUT_BETO, rut=RUT_BETO, email=correo, first_name='Beto de nuevo')
        self.assertEqual(registro.reaplicar(), 0)
        self.assertTrue(CustomUser.objects.filter(pk=nueva.pk).exists())

    def test_las_cuentas_ajenas_no_se_tocan(self):
        self.eliminar_a_beto()
        self.assertEqual(registro.reaplicar(), 0)
        self.assertTrue(CustomUser.objects.filter(pk=self.ana.user_id).exists())

    def test_una_cuenta_ya_seudonimizada_no_se_procesa_de_nuevo(self):
        paquete = dar_paquete(self.ana, self.profe, plan='flexible')
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, -3), paquete=paquete)
        registro.eliminar(self.ana.user)
        self.assertEqual(registro.reaplicar(), 0)

    def test_sin_registro_no_hace_nada(self):
        self.assertEqual(registro.reaplicar(), 0)


class ArchivoTests(Escenario):
    """Restaurar un respaldo devuelve tambien el registro a como estaba: el archivo conserva lo posterior."""

    def setUp(self):
        self.correo = self.beto.user.email
        registro.eliminar(self.beto.user)

    def test_exportar_e_importar_recupera_el_registro_perdido(self):
        filas = registro.exportar()
        RegistroSupresion.objects.all().delete()  # el respaldo restaurado no lo trae
        vuelta = volver_de_un_respaldo(RUT_BETO, self.correo)
        self.assertEqual(registro.reaplicar(), 0)  # sin registro, nadie sabe que hay que eliminarla
        self.assertEqual(registro.importar(filas), 1)
        self.assertEqual(registro.reaplicar(), 1)
        self.assertFalse(CustomUser.objects.filter(pk=vuelta.pk).exists())

    def test_importar_dos_veces_no_duplica(self):
        filas = registro.exportar()
        self.assertEqual(registro.importar(filas), 0)  # ya estaban
        RegistroSupresion.objects.all().delete()
        self.assertEqual(registro.importar(filas + filas), 1)
        self.assertEqual(RegistroSupresion.objects.count(), 1)

    def test_conserva_la_fecha_original(self):
        original = RegistroSupresion.objects.get().fecha
        filas = registro.exportar()
        RegistroSupresion.objects.all().delete()
        registro.importar(filas)
        self.assertEqual(RegistroSupresion.objects.get().fecha, original)

    def test_un_archivo_con_otro_formato_se_rechaza(self):
        for malo in ([{'rut': 'x', 'correo': '', 'fecha': '2026-11-03T10:00:00+00:00'}],  # huella corta
                     [{'rut': '', 'correo': ''}],  # sin fecha
                     [{'rut': '', 'correo': '', 'fecha': 'ayer'}],
                     [{'rut': 5, 'correo': '', 'fecha': '2026-11-03T10:00:00+00:00'}],
                     ['no es una fila']):
            with self.subTest(malo=malo), self.assertRaises(ValueError):
                registro.importar(malo)
        self.assertEqual(RegistroSupresion.objects.count(), 1)


class ComandosTests(Escenario):

    def setUp(self):
        self.correo = self.beto.user.email
        registro.eliminar(self.beto.user)
        self.carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(self.carpeta.cleanup)
        self.ruta = os.path.join(self.carpeta.name, 'supresiones.json')

    def correr(self, comando, *args):
        salida = StringIO()
        call_command(comando, *args, stdout=salida)
        return salida.getvalue()

    def test_exportar_escribe_el_archivo_y_solo_informa_cantidades(self):
        salida = self.correr('exportar_supresiones', self.ruta)
        self.assertEqual(salida.strip(), 'Supresiones exportadas: 1')
        with open(self.ruta, encoding='utf-8') as archivo:
            contenido = archivo.read()
        self.assertNotIn(RUT_BETO, contenido)
        self.assertNotIn(self.correo, contenido)
        self.assertEqual(json.loads(contenido)[0]['rut'], registro.huella(RUT_BETO))

    def test_exportar_en_una_ruta_imposible_da_error_claro(self):
        with self.assertRaises(CommandError):
            self.correr('exportar_supresiones', os.path.join(self.carpeta.name, 'no', 'existe', 'x.json'))

    def test_despues_de_restaurar_el_comando_elimina_de_nuevo_con_el_archivo(self):
        self.correr('exportar_supresiones', self.ruta)
        RegistroSupresion.objects.all().delete()
        vuelta = volver_de_un_respaldo(RUT_BETO, self.correo)
        salida = self.correr('reaplicar_supresiones', '--archivo', self.ruta)
        self.assertIn('Supresiones nuevas del archivo: 1', salida)
        self.assertIn('Cuentas eliminadas de nuevo: 1', salida)
        self.assertNotIn(RUT_BETO, salida)
        self.assertFalse(CustomUser.objects.filter(pk=vuelta.pk).exists())

    def test_simular_no_importa_ni_elimina_nada(self):
        self.correr('exportar_supresiones', self.ruta)
        RegistroSupresion.objects.all().delete()
        vuelta = volver_de_un_respaldo(RUT_BETO, self.correo)
        salida = self.correr('reaplicar_supresiones', '--archivo', self.ruta, '--simular')
        self.assertIn('Cuentas que se eliminarian: 1', salida)
        self.assertTrue(CustomUser.objects.filter(pk=vuelta.pk).exists())
        self.assertFalse(RegistroSupresion.objects.exists())  # tampoco quedo importado

    def test_sin_archivo_usa_el_registro_de_la_base(self):
        vuelta = volver_de_un_respaldo(RUT_BETO, self.correo)
        self.assertIn('Cuentas eliminadas de nuevo: 1', self.correr('reaplicar_supresiones'))
        self.assertFalse(CustomUser.objects.filter(pk=vuelta.pk).exists())

    def test_un_archivo_ilegible_o_con_otro_formato_da_error_claro(self):
        with self.assertRaises(CommandError):
            self.correr('reaplicar_supresiones', '--archivo', os.path.join(self.carpeta.name, 'nada.json'))
        with open(self.ruta, 'w', encoding='utf-8') as archivo:
            archivo.write('esto no es json')
        with self.assertRaises(CommandError):
            self.correr('reaplicar_supresiones', '--archivo', self.ruta)
        with open(self.ruta, 'w', encoding='utf-8') as archivo:
            json.dump({'no': 'es una lista'}, archivo)
        with self.assertRaises(CommandError):
            self.correr('reaplicar_supresiones', '--archivo', self.ruta)
