"""Videos del profesor (agregado de videos, fase 1): biblioteca en MongoDB con GridFS.

Mongo en memoria (mongomock): nunca se conecta a Atlas. Los MP4 se arman a mano con lo mínimo que lee
videoteca.duracion_mp4 (cajas ftyp, mdat y moov/mvhd).
"""

import io
import struct

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from comunidad import mongo
from comunidad.tests.base import GridFsTestCase
from tests.test_paquetes import RUT_ANA, RUT_OTRO, RUT_PROFE, Escenario
from user_profesor import videoteca


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


class VideotecaTests(GridFsTestCase, Escenario):

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

    @override_settings(MONGODB_URI=None)
    def test_sin_mongo_avisa_y_no_se_cae(self):
        mongo.restablecer()
        datos = self.listar()
        self.assertFalse(datos['disponible'])
        self.assertFalse(self.subir()['disponible'])

    def test_la_pestana_ya_no_trae_datos_inventados_ni_la_variable_que_faltaba(self):
        pagina = self.client.get(reverse('panel_profesor')).content.decode()
        for falso in ('1.428 vistas', '84.2 hrs', 'Universidad Python', 'teacherVideos'):
            with self.subTest(falso=falso):
                self.assertNotIn(falso, pagina)
