"""Documentos de apoderados (carnet y documento del vinculo).

Datos ficticios. Cubre la subida (cifrado, sin metadatos, solo JPG o PNG de hasta
5 MB, documento segun parentesco), la revision (sin documento no se aprueba; al
decidir se borra), el visor (solo administradores, marca de agua y registro de
cada apertura) y el borrado a los 30 dias.
"""

import io
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from alumnos.models import Tutor
from apoderados.documentos import descifrar
from apoderados.models import AccesoDocumento, Apoderado, Documento, Vinculo
from tests.test_apoderados import CLAVE, RUT, adjuntar, crear_apoderado, datos_registro, entrar, imagen
from tests.test_apoderados_adolescentes import CORREO_MAMA, crear_adolescente, url_invitacion
from tests.test_apoderados_vinculos import RUT_HERMANA, crear_menor_vinculado, datos_estudiante

User = get_user_model()
MARCA = 'Camara-Ficticia-GPS'


def crear_admin():
    admin = User.objects.create_user('10101010-1', password=CLAVE, rol='admin', first_name='Admin Revisora')
    return admin, Tutor.objects.create(user=admin)


class SubidaTests(TestCase):

    def registrar(self, **cambios):
        return self.client.post(reverse('registro_apoderado'), datos_registro(**cambios))

    def test_el_carnet_se_guarda_cifrado_y_sin_metadatos(self):
        exif = Image.Exif()
        exif[0x010F] = MARCA  # fabricante: como la ubicacion GPS, no debe guardarse
        self.registrar(carnet_frente=imagen('frente.jpg', exif=exif.tobytes()))

        apoderado = Apoderado.objects.get()
        self.assertEqual(sorted(apoderado.documentos.values_list('tipo', flat=True)), sorted(Documento.CARNET))
        frente = apoderado.documentos.get(tipo=Documento.CARNET_FRENTE)
        guardado = bytes(frente.contenido)
        self.assertNotIn(b'\xff\xd8', guardado[:4], 'el documento se guardo sin cifrar')
        claro = descifrar(guardado)
        self.assertNotIn(MARCA.encode(), claro, 'se guardaron los metadatos de la foto')
        self.assertEqual(Image.open(io.BytesIO(claro)).format, 'JPEG')

    def test_solo_acepta_imagenes_jpg_o_png_de_hasta_5_mb(self):
        formato, pesado = 'Sube una foto o imagen en formato JPG o PNG.', 'El archivo no puede superar los 5 MB.'
        casos = {
            'pdf': (SimpleUploadedFile('carnet.jpg', b'%PDF-1.4 documento falso'), formato),
            'gif': (imagen('carnet.gif', 'GIF'), formato),
            'pesado': (SimpleUploadedFile('carnet.jpg', b'0' * (5 * 1024 * 1024 + 1)), pesado),
        }
        for nombre, (archivo, error) in casos.items():
            with self.subTest(nombre):
                respuesta = self.registrar(carnet_frente=archivo)
                self.assertEqual(respuesta.context['form'].errors['carnet_frente'], [error])
        self.assertFalse(Apoderado.objects.exists())

    def test_el_formulario_envia_archivos_y_avisa_como_se_tratan(self):
        # Sin enctype el navegador no envia los archivos (el cliente de pruebas si, por eso se revisa aqui).
        respuesta = self.client.get(reverse('registro_apoderado'))
        self.assertContains(respuesta, 'enctype="multipart/form-data"')
        self.assertContains(respuesta, 'id="id_carnet_frente_helptext"')
        self.assertContains(respuesta, 'se elimina apenas la aprueba o la rechaza')

    def test_exige_el_carnet_por_ambos_lados(self):
        datos = datos_registro()
        del datos['carnet_reverso']
        respuesta = self.client.post(reverse('registro_apoderado'), datos)
        self.assertIn('carnet_reverso', respuesta.context['form'].errors)
        self.assertFalse(Apoderado.objects.exists())

    def test_el_documento_del_vinculo_depende_del_parentesco(self):
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)
        url = reverse('apoderado_registrar_estudiante')
        self.client.post(url, datos_estudiante(parentesco='madre'))
        self.client.post(url, datos_estudiante(parentesco='tutor', rut=RUT_HERMANA, nombre='Sofía Ficticia'))
        tipos = {v.parentesco: v.documentos.get().tipo for v in Vinculo.objects.all()}
        self.assertEqual(tipos, {'madre': Documento.CERTIFICADO, 'tutor': Documento.RESOLUCION})

    def test_aceptar_una_invitacion_exige_el_certificado_y_no_admite_tutores(self):
        # La invitacion del adolescente (1b-ii) es para su madre o su padre; el tutor entra por 1b-i.
        invitacion = crear_adolescente().invitar(CORREO_MAMA)
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)
        url = url_invitacion(invitacion)
        self.client.post(url, {'parentesco': 'madre', 'acepta_declaracion': 'on'})
        self.client.post(url, {'parentesco': 'tutor', 'acepta_declaracion': 'on', 'documento': imagen()})
        self.assertFalse(Vinculo.objects.exists())

        self.client.post(url, {'parentesco': 'madre', 'acepta_declaracion': 'on', 'documento': imagen()})
        self.assertEqual(Vinculo.objects.get().documentos.get().tipo, Documento.CERTIFICADO)


class RevisionConDocumentosTests(TestCase):

    def setUp(self):
        self.admin, tutor = crear_admin()
        self.apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        entrar(self.client, self.admin, admin_id=tutor.id_tutor)

    def aprobar_identidad(self):
        self.client.post(reverse('apoderado_revisar', args=[self.apoderado.pk]),
                         {'decision': 'aprobar', 'rut_coincide': 'on'})
        self.apoderado.refresh_from_db()

    def test_sin_el_documento_completo_no_se_aprueba(self):
        adjuntar(Documento.CARNET_FRENTE, apoderado=self.apoderado)  # falta el reverso
        self.aprobar_identidad()
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)

        Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.VERIFICADO)
        vinculo = crear_menor_vinculado(self.apoderado, estado=Vinculo.PENDIENTE)
        self.client.post(reverse('apoderado_revisar_vinculo', args=[vinculo.pk]),
                         {'decision': 'aprobar', 'certificado_coincide': 'on'})
        vinculo.refresh_from_db()
        self.assertEqual(vinculo.estado, Vinculo.PENDIENTE)

    def test_aprobar_o_rechazar_borra_los_documentos(self):
        for tipo in Documento.CARNET:
            adjuntar(tipo, apoderado=self.apoderado)
        self.aprobar_identidad()
        self.assertEqual(self.apoderado.estado, Apoderado.VERIFICADO)
        self.assertFalse(self.apoderado.documentos.exists())

        vinculo = crear_menor_vinculado(self.apoderado, estado=Vinculo.PENDIENTE)
        adjuntar(Documento.CERTIFICADO, vinculo=vinculo)
        self.client.post(reverse('apoderado_revisar_vinculo', args=[vinculo.pk]),
                         {'decision': 'rechazar', 'observacion': 'El certificado no se lee.'})
        vinculo.refresh_from_db()
        self.assertEqual(vinculo.estado, Vinculo.RECHAZADO)
        self.assertFalse(Documento.objects.exists())


class VisorDeDocumentosTests(TestCase):

    def setUp(self):
        self.admin, self.tutor = crear_admin()
        self.apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        self.documento = adjuntar(Documento.CARNET_FRENTE, apoderado=self.apoderado)
        self.url = reverse('apoderado_documento', args=[self.documento.pk])

    def test_solo_un_administrador_lo_ve(self):
        self.assertRedirects(self.client.get(self.url), reverse('login'), fetch_redirect_response=False)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        self.assertRedirects(self.client.get(self.url), reverse('portal_apoderado'), fetch_redirect_response=False)
        self.assertFalse(AccesoDocumento.objects.exists())

    def test_se_ve_con_marca_de_agua_sin_cache_y_queda_registrado(self):
        entrar(self.client, self.admin, admin_id=self.tutor.id_tutor)
        respuesta = self.client.get(self.url)

        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'image/jpeg'))
        self.assertIn('no-store', respuesta['Cache-Control'])
        self.assertNotEqual(respuesta.content, descifrar(self.documento.contenido), 'se mostro sin marca de agua')
        acceso = AccesoDocumento.objects.get()
        self.assertEqual((acceso.administrador, acceso.apoderado, acceso.tipo),
                         (self.admin, self.apoderado, Documento.CARNET_FRENTE))

    def test_la_bandeja_enlaza_los_documentos_y_el_registro_queda_al_borrarlos(self):
        entrar(self.client, self.admin, admin_id=self.tutor.id_tutor)
        self.assertContains(self.client.get(reverse('apoderados_revision')), self.url)
        self.client.get(self.url)
        self.documento.delete()
        self.assertEqual(AccesoDocumento.objects.count(), 1)


class VencimientoTests(TestCase):

    def test_el_comando_borra_los_documentos_de_mas_de_30_dias(self):
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        viejo = adjuntar(Documento.CARNET_FRENTE, apoderado=apoderado)
        reciente = adjuntar(Documento.CARNET_REVERSO, apoderado=apoderado)
        Documento.objects.filter(pk=viejo.pk).update(subido=timezone.now() - timedelta(days=31))

        call_command('borrar_documentos_vencidos', stdout=io.StringIO())

        self.assertEqual(list(Documento.objects.values_list('pk', flat=True)), [reciente.pk])
