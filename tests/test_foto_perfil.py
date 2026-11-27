"""Foto de perfil del profesor.

Se valida, se re-codifica a JPEG sin EXIF (las fotos de celular traen GPS), se
guarda en PostgreSQL (alumnos.FotoPerfil) y se sirve con la misma regla que el
perfil publico.
"""

import importlib
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from alumnos.models import Especialidad, FotoPerfil, Genero, Profesor
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_progreso_alumno import crear_alumno
from user_profesor import foto

RUT_ANA, RUT_PROFE, RUT_REVISION = '11111111-1', '22222222-2', '33333333-3'  # validos: el perfil valida el RUT
MIGRACION = importlib.import_module('alumnos.migrations.0045_fotos_perfil_en_base')


def imagen(formato='PNG', tamano=(1200, 900), modo='RGB', color='red', **opciones):
    buffer = BytesIO()
    Image.new(modo, tamano, color).save(buffer, formato, **opciones)
    return SimpleUploadedFile(f'foto.{formato.lower()}', buffer.getvalue())


def con_exif(marca):
    exif = Image.Exif()
    exif[0x010F] = marca  # Make; con GPS pasa igual
    return imagen('JPEG', exif=exif.tobytes())


def abrir_guardada(user):
    contenido = foto.leer(user.pk)
    return contenido, Image.open(BytesIO(contenido))


class FotoPerfilTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        crear_alumno(RUT_ANA, 'Ana', genero)
        cls.especialidad = Especialidad.objects.create(nombre='Química')
        cls.profe = crear_profesor(RUT_PROFE, 'profe@lbwus.cl', cls.especialidad)
        cls.en_revision = crear_profesor(RUT_REVISION, 'otro@lbwus.cl', cls.especialidad,
                                         titulo_estado=Profesor.TITULO_EN_REVISION)

    def entrar(self, rut):
        self.client.logout()
        self.client.post(reverse('login'), {'username': rut, 'password': CLAVE})

    def subir(self, archivo, profesor=None, **cambios):
        user = (profesor or self.profe).user
        datos = {'nombre': user.first_name, 'rut': user.rut, 'especialidad': self.especialidad.pk,
                 'direccion': user.direccion, 'correo_electronico': user.email,
                 'telefono': user.telefono, 'genero': user.genero.id_genero, **cambios}
        if archivo is not None:
            datos['foto_perfil'] = archivo
        return self.client.post(reverse('actualizar_perfil_prof'), datos).json()

    def poner_foto(self, profesor):
        foto.guardar(profesor.user, foto.procesar(imagen()))

    def pedir_foto(self, profesor):
        return self.client.get(reverse('foto_profesor', args=[profesor.id_profesor]))

    # ------------------------------------------------------------ subida

    def test_foto_valida_se_guarda_en_la_base_como_jpeg_reducido(self):
        self.entrar(RUT_PROFE)
        self.assertTrue(self.subir(imagen())['success'])
        self.assertEqual(FotoPerfil.objects.filter(user=self.profe.user).count(), 1)
        _, guardada = abrir_guardada(self.profe.user)
        self.assertEqual(guardada.format, 'JPEG')
        self.assertEqual(max(guardada.size), foto.LADO_MAX)

    def test_quita_los_metadatos_exif(self):
        self.entrar(RUT_PROFE)
        self.subir(con_exif('Marca-Secreta'))
        contenido, guardada = abrir_guardada(self.profe.user)
        self.assertNotIn(b'Marca-Secreta', contenido)
        self.assertEqual(dict(guardada.getexif()), {})

    def test_transparencia_queda_blanca(self):
        self.entrar(RUT_PROFE)
        self.subir(imagen(modo='RGBA', color=(0, 0, 0, 0)))
        _, guardada = abrir_guardada(self.profe.user)
        self.assertTrue(all(canal > 250 for canal in guardada.getpixel((0, 0))))

    def test_archivo_que_no_es_imagen_no_guarda_nada(self):
        self.entrar(RUT_PROFE)
        r = self.subir(SimpleUploadedFile('foto.png', b'esto no es una imagen'), nombre='Otro Nombre')
        self.assertEqual(r, {'success': False, 'message': 'El archivo no es una imagen válida.'})
        self.profe.user.refresh_from_db()
        self.assertEqual(self.profe.user.first_name, 'Profe')
        self.assertIsNone(foto.leer(self.profe.user.pk))

    def test_formato_no_permitido(self):
        self.entrar(RUT_PROFE)
        self.assertIn('Formato no permitido', self.subir(imagen('GIF'))['message'])

    def test_foto_muy_grande(self):
        self.entrar(RUT_PROFE)
        enorme = SimpleUploadedFile('foto.jpg', b'0' * (foto.MAX_MB * 1024 * 1024 + 1))
        self.assertEqual(self.subir(enorme)['message'], 'La foto supera los 5 MB.')

    def test_nueva_foto_reemplaza_la_anterior(self):
        self.entrar(RUT_PROFE)
        self.subir(imagen())
        anterior = foto.leer(self.profe.user.pk)
        self.subir(imagen(color='blue'))
        self.assertNotEqual(foto.leer(self.profe.user.pk), anterior)
        self.assertEqual(FotoPerfil.objects.filter(user=self.profe.user).count(), 1)

    def test_sin_foto_el_perfil_se_guarda_igual(self):
        self.entrar(RUT_PROFE)
        self.assertTrue(self.subir(None, nombre='Profe Nuevo')['success'])
        self.profe.user.refresh_from_db()
        self.assertEqual(self.profe.user.first_name, 'Profe Nuevo')
        self.assertIsNone(foto.leer(self.profe.user.pk))

    # ------------------------------------------------------------ quien la ve

    def test_el_profesor_ve_su_foto_aunque_no_este_habilitado(self):
        self.poner_foto(self.en_revision)
        self.entrar(RUT_REVISION)
        r = self.pedir_foto(self.en_revision)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/jpeg')

    def test_alumno_ve_la_foto_de_un_profesor_habilitado(self):
        self.poner_foto(self.profe)
        self.entrar(RUT_ANA)
        self.assertEqual(self.pedir_foto(self.profe).status_code, 200)

    def test_alumno_no_ve_la_foto_de_un_profesor_no_habilitado(self):
        self.poner_foto(self.en_revision)
        self.entrar(RUT_ANA)
        self.assertEqual(self.pedir_foto(self.en_revision).status_code, 404)

    def test_sin_sesion_no_se_ve(self):
        self.poner_foto(self.profe)
        self.assertEqual(self.pedir_foto(self.profe).status_code, 404)

    def test_sin_foto_responde_404(self):
        self.entrar(RUT_ANA)
        self.assertEqual(self.pedir_foto(self.profe).status_code, 404)

    # ------------------------------------------------------------ pantallas

    def test_perfil_publico_muestra_la_foto(self):
        self.poner_foto(self.profe)
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('perfil_profesor', args=[self.profe.id_profesor]))
        url = reverse('foto_profesor', args=[self.profe.id_profesor])
        self.assertContains(r, f'src="{url}"')
        self.assertContains(r, 'alt="Foto de Profe"')

    def test_panel_muestra_la_foto_con_la_url_protegida(self):
        self.poner_foto(self.profe)
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, f'src="{reverse("foto_profesor", args=[self.profe.id_profesor])}"')
        self.assertNotContains(r, '/media/perfiles/')

    def test_sin_foto_el_panel_muestra_el_icono(self):
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'))
        self.assertNotContains(r, reverse('foto_profesor', args=[self.profe.id_profesor]))
        self.assertContains(r, 'Elegir foto')

    def test_tiene_foto_se_entera_del_cambio_en_el_mismo_objeto(self):
        user = self.profe.user
        self.assertFalse(user.tiene_foto)
        foto.guardar(user, foto.procesar(imagen()))
        self.assertTrue(user.tiene_foto)
        foto.borrar(user)
        self.assertFalse(user.tiene_foto)


class MigracionFotosEnDiscoTests(SimpleTestCase):
    """0045: las fotos que estaban en MEDIA_ROOT/perfiles/ pasan a la base, limpias, y salen del disco."""

    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        ajuste = override_settings(MEDIA_ROOT=carpeta.name)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.media = Path(carpeta.name)

    def en_disco(self, nombre, contenido):
        ruta = self.media / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)
        return nombre

    def test_una_foto_antigua_con_exif_llega_limpia(self):
        nombre = self.en_disco('perfiles/vieja.jpg', con_exif('GPS-de-la-casa').read())
        jpeg = MIGRACION.foto_limpia(nombre)
        self.assertNotIn(b'GPS-de-la-casa', jpeg)
        self.assertEqual(Image.open(BytesIO(jpeg)).format, 'JPEG')

    def test_archivo_perdido_o_que_no_es_imagen_no_se_pasa(self):
        self.assertIsNone(MIGRACION.foto_limpia('perfiles/no_existe.jpg'))
        self.assertIsNone(MIGRACION.foto_limpia(self.en_disco('perfiles/falsa.jpg', b'<?php echo 1; ?>')))

    def test_borra_del_disco_aunque_alguna_ya_no_este(self):
        nombre = self.en_disco('perfiles/a.jpg', b'x')
        MIGRACION.borrar_del_disco([nombre, 'perfiles/no_existe.jpg'])
        self.assertFalse(default_storage.exists(nombre))
