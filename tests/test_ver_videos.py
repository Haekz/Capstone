"""Ver los videos compartidos (agregado de videos, fase 3b): alumno y apoderado.

Lo importante es la seguridad: un video solo se ve si el profesor se lo compartió a ESE alumno y su paquete sigue
vigente; en cualquier otro caso la respuesta es 404 (no se revela si el video existe). También soporta Range,
que es lo que permite adelantar y retroceder en el reproductor. Mongo en memoria (mongomock).
"""

from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from alumnos.models import PaqueteClases
from alumnos.models.videos import VideoCompartido
from apoderados.models import Apoderado
from comunidad import mongo
from comunidad.tests.base import GridFsTestCase
from tests.test_apoderados import crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, RUT_BETO, RUT_PROFE, Escenario
from tests.test_videoteca import archivo, mp4
from user_profesor import videoteca

# RUT propios de esta prueba: no deben repetirse con los del escenario base.
RUT_APODERADO, RUT_MENOR = '66666666-6', '77777777-7'
RUT_OTRO_APODERADO, RUT_OTRO_MENOR = '99999999-9', '88888888-8'


def cuerpo(respuesta):
    return b''.join(respuesta.streaming_content)


class Base(GridFsTestCase, Escenario):

    def setUp(self):
        super().setUp()
        self.contenido = mp4(1500)
        self.video = self.subir('Factorización', self.contenido)

    def subir(self, titulo, contenido=None):
        return videoteca.subir(self.profe.id_profesor, self.clase.asignatura_id, titulo,
                               archivo(contenido=contenido if contenido is not None else mp4(1500)))

    def compartir(self, alumno, video=None, dias_restantes=60, estado=PaqueteClases.ESTADO_ACTIVA):
        paquete = PaqueteClases.objects.create(
            alumno=alumno, profesor=self.profe, plan='progreso', clases=4, tarifa=15000, monto=59000, videos=4,
            monto_videos=20000, dias=60, buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=estado,
            fecha_fin=timezone.now() + timedelta(days=dias_restantes))
        VideoCompartido.objects.create(paquete=paquete, video_id=video or self.video)
        return paquete


class VerVideosDelAlumnoTests(Base):

    def setUp(self):
        super().setUp()
        self.compartir(self.ana)
        self.entrar(RUT_ANA)

    def ver(self, video=None, **extra):
        return self.client.get(reverse('ver_video', args=[video or self.video]), **extra)

    def test_lista_solo_lo_que_le_compartieron_con_los_datos_para_mostrar(self):
        self.compartir(self.beto, self.subir('Solo de Beto'))
        self.compartir(self.ana, self.subir('Vencido'), dias_restantes=-1)
        self.compartir(self.ana, self.subir('Pendiente'), estado=PaqueteClases.ESTADO_PENDIENTE)
        datos = self.client.get(reverse('videos_alumno')).json()
        self.assertTrue(datos['disponible'])
        self.assertEqual(datos['videos'], [{'id': self.video, 'titulo': 'Factorización', 'asignatura': 'Algebra',
                                            'duracion': '25:00', 'profesor': self.profe.nombre}])

    def test_si_el_profesor_borro_el_video_no_se_lista_ni_se_cae(self):
        videoteca.eliminar(self.profe.id_profesor, self.video)
        self.assertEqual(self.client.get(reverse('videos_alumno')).json()['videos'], [])
        self.assertEqual(self.ver().status_code, 404)

    def test_entrega_el_video_completo(self):
        r = self.ver()
        self.assertEqual((r.status_code, r['Content-Type'], r['Accept-Ranges']), (200, 'video/mp4', 'bytes'))
        self.assertEqual(int(r['Content-Length']), len(self.contenido))
        self.assertEqual(cuerpo(r), self.contenido)

    def test_rangos_para_adelantar_y_retroceder(self):
        total = len(self.contenido)
        for cabecera, desde, hasta in (('bytes=0-9', 0, 9), ('bytes=5-', 5, total - 1), ('bytes=-10', total - 10, total - 1),
                                       ('bytes=0-999999999', 0, total - 1)):
            with self.subTest(cabecera=cabecera):
                r = self.ver(HTTP_RANGE=cabecera)
                self.assertEqual(r.status_code, 206)
                self.assertEqual(r['Content-Range'], f'bytes {desde}-{hasta}/{total}')
                self.assertEqual(cuerpo(r), self.contenido[desde:hasta + 1])
                self.assertEqual(int(r['Content-Length']), hasta - desde + 1)

    def test_rango_fuera_del_archivo_da_416_y_el_mal_escrito_se_ignora(self):
        total = len(self.contenido)
        for cabecera in ('bytes=999999999-', f'bytes={total}-', 'bytes=-0'):
            with self.subTest(cabecera=cabecera):
                r = self.ver(HTTP_RANGE=cabecera)
                self.assertEqual((r.status_code, r['Content-Range']), (416, f'bytes */{total}'))
        for cabecera in ('bytes=9-3', 'bytes=abc', 'bytes=-', 'items=0-1', 'bytes=0-1,3-4', ''):  # RFC 7233: se ignoran
            with self.subTest(cabecera=cabecera):
                self.assertEqual(self.ver(HTTP_RANGE=cabecera).status_code, 200)

    def test_nadie_mas_lo_ve(self):
        self.assertEqual(self.ver(self.subir('No compartido')).status_code, 404)  # existe, pero no es de ella
        self.assertEqual(self.ver('no-es-id').status_code, 404)
        self.assertEqual(self.ver('0' * 24).status_code, 404)
        self.entrar(RUT_BETO)  # otro alumno
        self.assertEqual(self.ver().status_code, 404)
        self.assertEqual(self.client.get(reverse('videos_alumno')).json()['videos'], [])
        self.client.logout()  # sin sesión
        self.assertEqual(self.ver().status_code, 302)
        self.entrar(RUT_PROFE)  # un profesor tampoco es alumno
        self.assertEqual(self.ver().status_code, 302)

    def test_con_el_paquete_vencido_o_pendiente_ya_no_se_ve(self):
        otro = self.subir('Otro')
        self.compartir(self.ana, otro, dias_restantes=-1)
        pendiente = self.compartir(self.ana, self.subir('Pendiente'), estado=PaqueteClases.ESTADO_PENDIENTE)
        self.assertEqual(self.ver(otro).status_code, 404)
        self.assertEqual(self.ver(VideoCompartido.objects.get(paquete=pendiente).video_id).status_code, 404)
        PaqueteClases.objects.filter(alumno=self.ana, videos_compartidos__video_id=self.video).update(
            fecha_fin=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.ver().status_code, 404)  # y el que sí era suyo, al vencer, desaparece

    @override_settings(MONGODB_URI=None)
    def test_sin_mongo_avisa_y_no_se_cae(self):
        mongo.restablecer()
        self.assertFalse(self.client.get(reverse('videos_alumno')).json()['disponible'])
        self.assertEqual(self.ver().status_code, 503)

    def test_el_panel_ya_no_trae_los_videos_inventados(self):
        pagina = self.client.get(reverse('alumno_pag1')).content.decode()
        for falso in ('Leyes de la Termodin', 'Imperio Romano', 'Phrasal Verbs', 'aún no hay clases en video'):
            with self.subTest(falso=falso):
                self.assertNotIn(falso, pagina)
        self.assertIn(reverse('videos_alumno'), pagina)


class VerVideosDelApoderadoTests(Base):

    def setUp(self):
        super().setUp()
        self.apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR)
        self.compartir(self.vinculo.alumno)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def lista(self, vinculo=None):
        return self.client.get(reverse('apoderado_videos_estudiante', args=[(vinculo or self.vinculo).pk]))

    def ver(self, video=None, vinculo=None, **extra):
        return self.client.get(reverse('apoderado_ver_video', args=[(vinculo or self.vinculo).pk, video or self.video]),
                               **extra)

    def test_ve_y_reproduce_los_videos_de_su_estudiante(self):
        self.assertEqual([v['titulo'] for v in self.lista().json()['videos']], ['Factorización'])
        r = self.ver(HTTP_RANGE='bytes=0-9')
        self.assertEqual((r.status_code, cuerpo(r)), (206, self.contenido[:10]))
        self.assertEqual(cuerpo(self.ver()), self.contenido)

    def test_la_pagina_de_clases_trae_los_videos(self):
        pagina = self.client.get(reverse('apoderado_clases_estudiante', args=[self.vinculo.pk])).content.decode()
        self.assertIn(reverse('apoderado_videos_estudiante', args=[self.vinculo.pk]), pagina)

    def test_no_ve_el_video_de_otro_estudiante_ni_estudiantes_ajenos(self):
        self.compartir(self.ana, self.subir('De Ana'))  # una alumna cualquiera
        de_ana = VideoCompartido.objects.get(paquete__alumno=self.ana).video_id
        self.assertEqual(self.ver(de_ana).status_code, 404)  # no es de su estudiante
        otro = crear_apoderado(RUT_OTRO_APODERADO, Apoderado.VERIFICADO)
        ajeno = crear_menor_vinculado(otro, rut=RUT_OTRO_MENOR)
        self.assertEqual(self.lista(ajeno).status_code, 404)  # su vínculo, no el mío
        self.assertEqual(self.ver(vinculo=ajeno).status_code, 404)

    def test_con_el_paquete_vencido_ya_no_se_ve(self):
        PaqueteClases.objects.filter(alumno=self.vinculo.alumno).update(fecha_fin=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.lista().json()['videos'], [])
        self.assertEqual(self.ver().status_code, 404)

    def test_sin_sesion_de_apoderado_no_entra(self):
        self.client.logout()
        self.assertEqual(self.ver().status_code, 302)
        self.assertEqual(self.lista().status_code, 302)
