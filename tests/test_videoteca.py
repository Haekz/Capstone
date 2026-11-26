"""Videos del profesor (agregado de videos, fase 1): el archivo en Cloudflare R2 y su ficha en la tabla Video.

Un R2 de mentira (tests/videos_base.py): nunca se conecta a Cloudflare.
Los MP4 se arman a mano con lo mínimo que lee videoteca.duracion_mp4 (cajas ftyp, mdat y moov/mvhd).
"""

import io
import struct
from unittest import mock

from botocore.exceptions import ClientError
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from alumnos.models import Video
from tests.test_paquetes import RUT_ANA, RUT_OTRO, RUT_PROFE, Escenario
from tests.videos_base import VideosTestCase
from user_profesor import almacen_videos, videoteca


def caja(tipo, contenido):
    return struct.pack('>I4s', 8 + len(contenido), tipo) + contenido


def mp4(segundos, version=0, escala=1000):
    """MP4 mínimo con el moov al final, como lo guardan muchos celulares."""
    if version == 1:
        mvhd = b'\x01\0\0\0' + bytes(16) + struct.pack('>IQ', escala, int(segundos * escala))
    else:
        mvhd = bytes(4) + bytes(8) + struct.pack('>II', escala, int(segundos * escala))
    return (caja(b'ftyp', b'isom\0\0\2\0isommp41') + caja(b'mdat', bytes(32))
            + caja(b'moov', caja(b'mvhd', mvhd + bytes(80))))


def archivo(segundos=25 * 60, nombre='clase.mp4', contenido=None):
    return SimpleUploadedFile(nombre, contenido if contenido is not None else mp4(segundos), 'video/mp4')


class DuracionMp4Tests(SimpleTestCase):

    def test_lee_la_duracion_en_las_dos_versiones(self):
        self.assertEqual(videoteca.duracion_mp4(io.BytesIO(mp4(1500))), 1500)
        self.assertEqual(videoteca.duracion_mp4(io.BytesIO(mp4(90.5, version=1, escala=600))), 90.5)

    def test_rechaza_lo_que_no_es_mp4(self):
        for malo in (b'', b'\x89PNG\r\n\x1a\n' + bytes(40), mp4(60)[:30], caja(b'ftyp', b'isom')):
            with self.subTest(malo=malo[:12]), self.assertRaises(ValidationError):
                videoteca.duracion_mp4(io.BytesIO(malo))


class VideotecaTests(VideosTestCase, Escenario):

    def setUp(self):
        super().setUp()
        self.entrar(RUT_PROFE)

    def subir(self, **datos):
        datos = {'titulo': 'Factorización', 'asignatura': self.clase.asignatura_id, 'archivo': archivo(), **datos}
        return self.client.post(reverse('subir_video'), datos).json()

    def listar(self):
        return self.client.get(reverse('videos_profesor')).json()

    def test_sube_y_lista_sus_videos_con_sus_materias(self):
        self.assertTrue(self.subir()['success'])
        datos = self.listar()
        self.assertEqual(datos['asignaturas'], [{'id': self.clase.asignatura_id, 'nombre': 'Algebra'}])
        [video] = datos['videos']
        self.assertEqual((video['titulo'], video['asignatura'], video['duracion']), ('Factorización', 'Algebra', '25:00'))

    def test_el_archivo_queda_en_r2_con_el_id_de_su_ficha(self):
        self.subir(archivo=archivo(contenido=mp4(600)))
        [video] = self.listar()['videos']
        self.assertEqual(self.r2.objetos, {f'videos/{video["id"]}.mp4': (mp4(600), 'video/mp4')})
        self.assertEqual(videoteca.ficha(video['id']).duracion_seg, 600)

    def test_al_borrarlo_se_va_de_la_base_y_de_r2(self):
        self.subir()
        [video] = self.listar()['videos']
        self.assertTrue(self.client.post(reverse('eliminar_video', args=[video['id']])).json()['success'])
        self.assertIsNone(videoteca.ficha(video['id']))
        self.assertEqual(self.r2.objetos, {})

    def test_si_la_base_falla_despues_de_subir_no_queda_el_archivo_huerfano_en_r2(self):
        with mock.patch.object(Video.objects, 'create', side_effect=DatabaseError('caida')), \
                self.assertRaises(DatabaseError):
            videoteca.subir(self.profe.pk, self.clase.asignatura_id, 'Factorización', archivo())
        self.assertEqual(self.r2.objetos, {})

    def test_si_r2_falla_al_borrar_el_video_igual_sale_de_la_biblioteca(self):
        self.subir()
        [video] = self.listar()['videos']
        falla = ClientError({'Error': {'Code': 'InternalError'}}, 'DeleteObject')
        with mock.patch.object(self.r2, 'delete_object', side_effect=falla):
            self.assertTrue(self.client.post(reverse('eliminar_video', args=[video['id']])).json()['success'])
        self.assertEqual(self.listar()['videos'], [])  # queda un archivo huerfano en R2: solo ocupa espacio

    @override_settings(R2_CONFIGURADO=False)
    def test_sin_r2_avisa_al_subir_y_no_se_cae(self):
        almacen_videos.restablecer()
        r = self.subir()
        self.assertEqual((r['success'], r['disponible']), (False, False))
        self.assertEqual(Video.objects.count(), 0)  # sin archivo no hay ficha

    def test_rechaza_videos_de_mas_de_30_minutos(self):
        r = self.subir(archivo=archivo(30 * 60 + 1))
        self.assertFalse(r['success'])
        self.assertIn('30 minutos', r['message'])
        self.assertTrue(self.subir(archivo=archivo(30 * 60))['success'])

    def test_rechaza_materias_que_no_ensena_archivos_que_no_son_mp4_y_titulos_vacios(self):
        for datos in ({'asignatura': 999999}, {'asignatura': 'abc'}, {'titulo': '  '},
                      {'archivo': archivo(contenido=b'no soy un video')}, {'archivo': ''}):
            with self.subTest(datos=datos):
                self.assertFalse(self.subir(**datos)['success'])
        self.assertEqual(self.listar()['videos'], [])

    def test_solo_borra_sus_propios_videos(self):
        self.subir()
        [video] = self.listar()['videos']
        self.entrar(RUT_OTRO)
        self.assertFalse(self.client.post(reverse('eliminar_video', args=[video['id']])).json()['success'])
        self.assertEqual(self.listar()['videos'], [])  # el otro profesor no ve videos ajenos
        self.entrar(RUT_PROFE)
        self.assertEqual(len(self.listar()['videos']), 1)
        self.assertTrue(self.client.post(reverse('eliminar_video', args=[video['id']])).json()['success'])
        self.assertEqual(self.listar()['videos'], [])
        self.assertFalse(self.client.post(reverse('eliminar_video', args=['no-es-un-id'])).json()['success'])

    def test_un_alumno_no_entra(self):
        self.entrar(RUT_ANA)
        self.assertNotIn('videos', self.client.get(reverse('videos_profesor')).json())
        self.assertNotEqual(self.client.post(reverse('subir_video'), {}).status_code, 500)

    def test_sin_r2_la_biblioteca_avisa_y_no_se_cae_aunque_haya_fichas(self):
        self.assertTrue(self.subir()['success'])
        almacen_videos.restablecer()
        with override_settings(R2_CONFIGURADO=False):
            datos = self.listar()
        self.assertFalse(datos['disponible'])

    def test_la_pestana_ya_no_trae_datos_inventados_ni_la_variable_que_faltaba(self):
        pagina = self.client.get(reverse('panel_profesor')).content.decode()
        for falso in ('1.428 vistas', '84.2 hrs', 'Universidad Python', 'teacherVideos'):
            with self.subTest(falso=falso):
                self.assertNotIn(falso, pagina)
