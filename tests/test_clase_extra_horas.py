"""Clase extra, tramo B (commit 1): las horas que el alumno puede pedir y el pedido desde la pantalla.

Las reglas son las de solicitar() (tests/test_clase_extra.py). Aqui se prueba que la lista use todas, en el mismo
sentido, sin bloquear nada (solo muestra), y que las vistas respondan como la reserva normal: {success, message}.
"""

import json
from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from agenda.models import HorarioSemanal
from alumnos import clase_extra
from alumnos.exceptions import SinClasesDisponiblesError
from alumnos.models import Inscripcion, PaqueteClases, Profesor, SolicitudClaseExtra
from alumnos.services import InscripcionService, paquetes_vigentes
from tests.test_apoderados_vincular import crear_alumno as crear_alumno_con_edad
from tests.test_clase_extra import el_dia
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, Escenario, dar_paquete

DIAS = 3  # el dia que se mira: lejos de "ahora", asi la anticipacion no interfiere salvo donde se prueba


class Agenda(Escenario):
    """Ana tiene un paquete con el profesor. Ayudas para armarle la agenda al profesor ese dia."""

    def setUp(self):
        self.paquete = dar_paquete(self.ana, self.profe)
        self.dia = timezone.localdate() + timedelta(days=DIAS)

    def franja(self, desde, hasta):
        HorarioSemanal.objects.create(profesor=self.profe, dia_semana=self.dia.weekday(),
                                      hora_inicio=time(desde), hora_fin=time(hasta))

    def ocupar(self, hora):
        """El profesor ya tiene a Beto a esa hora."""
        sesion = crear_sesion(self.clase, dias=DIAS)
        sesion.fecha_hora_inicio = el_dia(DIAS, hora)
        sesion.fecha_hora_fin = el_dia(DIAS, hora) + timedelta(hours=1)
        sesion.save(skip_clean=True)
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase, sesion=sesion,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)


class HorasParaPedirTests(Agenda):

    def motivos(self, **extra):
        """{hora local: motivo} del dia, '' si se puede pedir."""
        return {timezone.localtime(inicio).hour: motivo
                for inicio, motivo in clase_extra.horas_para_pedir(self.ana, self.clase, self.dia, **extra)}

    def test_ofrece_de_8_a_21_en_punto_y_todas_libres_si_nada_choca(self):
        horas = clase_extra.horas_para_pedir(self.ana, self.clase, self.dia)
        self.assertEqual([timezone.localtime(i).hour for i, _ in horas], list(range(8, 22)))
        self.assertEqual({(timezone.localtime(i).minute, timezone.localtime(i).date()) for i, _ in horas},
                         {(0, self.dia)})
        self.assertEqual({m for _, m in horas}, {''})

    def test_las_horas_de_una_franja_semanal_quedan_fuera_aunque_no_tenga_bloques(self):
        self.franja(15, 17)
        motivos = self.motivos()
        for hora in (15, 16):
            self.assertIn('parte de los horarios del profesor', motivos[hora])
        self.assertEqual((motivos[14], motivos[17]), ('', ''))

    def test_una_hora_en_que_el_profesor_ya_tiene_clase_queda_fuera(self):
        self.ocupar(10)
        motivos = self.motivos()
        self.assertIn('ya tiene una clase a esa hora', motivos[10])
        self.assertEqual((motivos[9], motivos[11]), ('', ''))

    def test_el_mismo_dia_quedan_fuera_las_que_estan_a_menos_de_4_horas(self):
        motivos = self.motivos(ahora=el_dia(DIAS, 9))
        for hora in range(8, 13):
            self.assertIn('4 horas de anticipación', motivos[hora])
        self.assertEqual(motivos[13], '')  # justo 4 horas: se puede, como en solicitar()

    def test_las_que_caen_despues_del_vencimiento_del_paquete_quedan_fuera(self):
        PaqueteClases.objects.filter(pk=self.paquete.pk).update(fecha_fin=el_dia(DIAS, 12))
        motivos = self.motivos()
        self.assertEqual({motivos[h] for h in range(8, 13)}, {''})  # empieza a mas tardar al vencer
        self.assertIn('vence', motivos[13])

    def test_sin_clases_con_ese_profesor_no_hay_horas(self):
        self.paquete.delete()
        with self.assertRaisesMessage(SinClasesDisponiblesError, 'Compra un paquete en Planes'):
            clase_extra.horas_para_pedir(self.ana, self.clase, self.dia)

    def test_un_paquete_activo_pero_ya_gastado_no_cuenta(self):
        self.paquete.delete()
        dar_paquete(self.ana, self.profe, plan='flexible')
        InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=5).pk)  # su unica clase
        with self.assertRaisesMessage(SinClasesDisponiblesError, 'Compra un paquete en Planes'):
            clase_extra.horas_para_pedir(self.ana, self.clase, self.dia)

    def test_con_dos_paquetes_vale_el_que_vence_mas_tarde(self):
        PaqueteClases.objects.filter(pk=self.paquete.pk).update(fecha_fin=el_dia(DIAS, 12))
        otro = dar_paquete(self.ana, self.profe)
        PaqueteClases.objects.filter(pk=otro.pk).update(fecha_fin=el_dia(DIAS, 19))
        motivos = self.motivos()
        self.assertEqual({motivos[h] for h in range(8, 20)}, {''})
        self.assertIn('vence', motivos[20])

    def test_un_menor_no_la_pide_por_su_cuenta(self):
        menor = crear_alumno_con_edad('30000000-1', 12)
        dar_paquete(menor, self.profe)
        with self.assertRaisesMessage(ValidationError, 'menores de edad las hace su apoderado'):
            clase_extra.horas_para_pedir(menor, self.clase, self.dia)

    def test_con_un_profesor_sin_titulo_validado_no_hay_horas(self):
        Profesor.objects.filter(pk=self.profe.pk).update(titulo_estado=Profesor.TITULO_EN_REVISION)
        self.clase.profesor.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'título'):
            clase_extra.horas_para_pedir(self.ana, self.clase, self.dia)

    def test_solo_mira_no_bloquea_nada(self):
        with CaptureQueriesContext(connection) as consultas:
            clase_extra.horas_para_pedir(self.ana, self.clase, self.dia)
        self.assertFalse([q['sql'] for q in consultas if 'FOR UPDATE' in q['sql']])

    def test_lo_que_ofrece_es_exactamente_lo_que_solicitar_acepta(self):
        """La pantalla nunca ofrece algo que el servidor rechace, ni esconde algo que aceptaria."""
        self.franja(15, 17)
        self.ocupar(10)
        PaqueteClases.objects.filter(pk=self.paquete.pk).update(fecha_fin=el_dia(DIAS, 19))
        ahora = timezone.now()
        for inicio, motivo in clase_extra.horas_para_pedir(self.ana, self.clase, self.dia, ahora=ahora):
            with self.subTest(hora=timezone.localtime(inicio).hour, motivo=motivo):
                if motivo:
                    with self.assertRaises(ValidationError):
                        clase_extra.solicitar(self.ana, self.clase, inicio, ahora=ahora)
                else:
                    self.assertTrue(clase_extra.solicitar(self.ana, self.clase, inicio, ahora=ahora).pk)


class BloqueoDelPaqueteTests(Agenda):
    """services.paquetes_vigentes se separo del bloqueo: mirar no bloquea, gastar una clase si.

    El bloqueo impide que dos reservas simultaneas gasten la misma ultima clase; ninguna otra prueba notaba si se
    quitaba (lo detecto una mutacion).
    """

    def consultas_al_paquete(self, accion):
        tabla = PaqueteClases._meta.db_table
        with CaptureQueriesContext(connection) as consultas:
            accion()
        return [q['sql'] for q in consultas if tabla in q['sql']]

    def test_reservar_bloquea_el_paquete(self):
        sesion = crear_sesion(self.clase, dias=5)
        sql = self.consultas_al_paquete(lambda: InscripcionService.inscribir_alumno_en_sesion(self.ana, sesion.pk))
        self.assertTrue([q for q in sql if 'FOR UPDATE' in q])

    def test_consultar_los_paquetes_vigentes_no_bloquea(self):
        sql = self.consultas_al_paquete(lambda: list(paquetes_vigentes(self.ana, self.profe, timezone.now())))
        self.assertTrue(sql)
        self.assertFalse([q for q in sql if 'FOR UPDATE' in q])


class VistasTests(Agenda):

    def setUp(self):
        super().setUp()
        self.entrar(RUT_ANA)

    def horas(self, **params):
        datos = {'clase_id': self.clase.pk, 'fecha': self.dia.isoformat(), **params}
        return self.client.get(reverse('clase_extra_horas'), datos)

    def pedir(self, **datos):
        cuerpo = {'clase_id': self.clase.pk, 'inicio': el_dia(DIAS, 10).isoformat(), 'mensaje': 'Hola', **datos}
        return self.client.post(reverse('clase_extra_pedir'), json.dumps(cuerpo), content_type='application/json')

    # --- horas
    def test_lista_las_horas_del_dia_con_su_motivo(self):
        self.franja(15, 16)
        r = self.horas()
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        self.assertTrue(datos['success'])
        self.assertEqual(datos['fecha'], self.dia.isoformat())
        self.assertEqual([h['hora'] for h in datos['horas']], [f'{h:02d}:00' for h in range(8, 22)])
        quince = datos['horas'][7]
        self.assertEqual(quince['inicio'], el_dia(DIAS, 15).isoformat())
        self.assertIn('parte de los horarios', quince['motivo'])
        self.assertEqual(datos['horas'][6]['motivo'], '')

    def test_sin_paquete_explica_que_hay_que_comprar(self):
        self.paquete.delete()
        r = self.horas()
        self.assertEqual((r.status_code, r.json()['success']), (400, False))
        self.assertIn('Compra un paquete en Planes', r.json()['message'])

    def test_fecha_mal_escrita_o_pasada(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        for fecha in ('mañana', '', '2026-13-40', ayer):
            with self.subTest(fecha=fecha):
                r = self.horas(fecha=fecha)
                self.assertEqual((r.status_code, r.json()['success']), (400, False))

    def test_clase_que_no_existe_o_mal_escrita(self):
        for clase_id in ('999999', 'abc', ''):
            with self.subTest(clase_id=clase_id):
                self.assertEqual(self.horas(clase_id=clase_id).status_code, 404)

    # --- pedir
    def test_pedir_registra_la_solicitud_y_dice_hasta_cuando_responde(self):
        r = self.pedir()
        self.assertEqual(r.status_code, 200)
        datos = r.json()
        solicitud = SolicitudClaseExtra.objects.get()
        self.assertEqual((solicitud.alumno, solicitud.clase, solicitud.fecha_hora_inicio, solicitud.mensaje),
                         (self.ana, self.clase, el_dia(DIAS, 10), 'Hola'))
        self.assertTrue(datos['success'])
        self.assertEqual(datos['vence_el'], solicitud.vence_el.isoformat())
        self.assertIn(timezone.localtime(solicitud.vence_el).strftime('%d/%m/%Y a las %H:%M'), datos['message'])

    def test_pedir_una_hora_que_no_se_puede_explica_por_que_y_no_guarda_nada(self):
        self.franja(10, 11)
        r = self.pedir()
        self.assertEqual((r.status_code, r.json()['success']), (400, False))
        self.assertIn('parte de los horarios', r.json()['message'])
        self.assertFalse(SolicitudClaseExtra.objects.exists())

    def test_pedir_con_datos_que_no_sirven(self):
        casos = ({'inicio': 'mañana'}, {'inicio': ''}, {'inicio': '2026-11-20T10:00'}, {'clase_id': 'abc'},
                 {'mensaje': ['no', 'texto']})
        for datos in casos:
            with self.subTest(datos=datos):
                r = self.pedir(**datos)
                self.assertFalse(r.json()['success'])
                self.assertIn(r.status_code, (400, 404))
        self.assertFalse(SolicitudClaseExtra.objects.exists())

    def test_pedir_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('clase_extra_pedir')).status_code, 405)

    def test_sin_sesion_de_alumno_no_entra(self):
        self.client.logout()
        for r in (self.horas(), self.pedir()):
            self.assertEqual((r.status_code, r.json()['success']), (401, False))
        self.assertFalse(SolicitudClaseExtra.objects.exists())
