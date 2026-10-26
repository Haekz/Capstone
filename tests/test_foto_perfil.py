"""Foto de perfil del profesor (pendiente de SCRUM-32).

Antes el formulario tenia el campo pero ninguna vista guardaba el archivo, y
MEDIA_URL no esta publicado, asi que la foto nunca se podia mostrar.
Ahora: se valida, se re-codifica a JPEG sin EXIF (las fotos de celular traen
GPS) y se sirve con la misma regla que el perfil publico.
"""

import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from alumnos.models import Especialidad, Genero, Profesor
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_progreso_alumno import crear_alumno
from user_profesor import foto

RUT_ANA, RUT_PROFE, RUT_REVISION = '11111111-1', '22222222-2', '33333333-3'  # validos: el perfil valida el RUT


def imagen(formato='PNG', tamano=(1200, 900), modo='RGB', color='red', **opciones):
    buffer = BytesIO()
    Image.new(modo, tamano, color).save(buffer, formato, **opciones)
    return SimpleUploadedFile(f'foto.{formato.lower()}', buffer.getvalue())


def abrir_guardada(user):
    with user.foto_perfil.open('rb') as archivo:
        contenido = archivo.read()
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

    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

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
        profesor.user.save()

    def pedir_foto(self, profesor):
        r = self.client.get(reverse('foto_profesor', args=[profesor.id_profesor]))
        r.close()  # suelta el archivo: en Windows impide borrar la carpeta temporal
        return r

    # ------------------------------------------------------------ subida

    def test_foto_valida_se_guarda_como_jpeg_reducido(self):
        self.entrar(RUT_PROFE)
        self.assertTrue(self.subir(imagen())['success'])
        self.profe.user.refresh_from_db()
        self.assertRegex(self.profe.user.foto_perfil.name, r'^perfiles/[0-9a-f]{32}\.jpg$')
        _, guardada = abrir_guardada(self.profe.user)
        self.assertEqual(guardada.format, 'JPEG')
        self.assertEqual(max(guardada.size), foto.LADO_MAX)

    def test_quita_los_metadatos_exif(self):
        exif = Image.Exif()
        exif[0x010F] = 'Marca-Secreta'  # Make; con GPS pasa igual
        self.entrar(RUT_PROFE)
        self.subir(imagen('JPEG', exif=exif.tobytes()))
        self.profe.user.refresh_from_db()
        contenido, guardada = abrir_guardada(self.profe.user)
        self.assertNotIn(b'Marca-Secreta', contenido)
        self.assertEqual(dict(guardada.getexif()), {})

    def test_transparencia_queda_blanca(self):
        self.entrar(RUT_PROFE)
        self.subir(imagen(modo='RGBA', color=(0, 0, 0, 0)))
        self.profe.user.refresh_from_db()
        _, guardada = abrir_guardada(self.profe.user)
        self.assertTrue(all(canal > 250 for canal in guardada.getpixel((0, 0))))

    def test_archivo_que_no_es_imagen_no_guarda_nada(self):
        self.entrar(RUT_PROFE)
        r = self.subir(SimpleUploadedFile('foto.png', b'esto no es una imagen'), nombre='Otro Nombre')
        self.assertEqual(r, {'success': False, 'message': 'El archivo no es una imagen válida.'})
        self.profe.user.refresh_from_db()
        self.assertEqual(self.profe.user.first_name, 'Profe')
        self.assertFalse(self.profe.user.foto_perfil)

    def test_formato_no_permitido(self):
        self.entrar(RUT_PROFE)
        self.assertIn('Formato no permitido', self.subir(imagen('GIF'))['message'])

    def test_foto_muy_grande(self):
        self.entrar(RUT_PROFE)
        enorme = SimpleUploadedFile('foto.jpg', b'0' * (foto.MAX_MB * 1024 * 1024 + 1))
        self.assertEqual(self.subir(enorme)['message'], 'La foto supera los 5 MB.')

    def test_nueva_foto_reemplaza_y_borra_la_anterior(self):
        self.entrar(RUT_PROFE)
        self.subir(imagen())
        self.profe.user.refresh_from_db()
        anterior = self.profe.user.foto_perfil.name
        self.subir(imagen(color='blue'))
        self.profe.user.refresh_from_db()
        self.assertNotEqual(self.profe.user.foto_perfil.name, anterior)
        self.assertFalse(self.profe.user.foto_perfil.storage.exists(anterior))

    def test_sin_foto_el_perfil_se_guarda_igual(self):
        self.entrar(RUT_PROFE)
        self.assertTrue(self.subir(None, nombre='Profe Nuevo')['success'])
        self.profe.user.refresh_from_db()
        self.assertEqual(self.profe.user.first_name, 'Profe Nuevo')
        self.assertFalse(self.profe.user.foto_perfil)

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
