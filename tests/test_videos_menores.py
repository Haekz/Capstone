"""Videos de menores: el apoderado revisa cada video y recien ahi lo habilita para su estudiante (decidido 09-nov).

El menor no ve (ni en la lista ni por enlace directo) un video que su apoderado no habilito; el apoderado lo ve
todo para poder revisarlo. Cuando el profesor comparte un video con un menor, se avisa a sus apoderados verificados.
Un alumno adulto lo sigue viendo apenas se comparte. Mongo en memoria (mongomock).
"""

from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from alumnos.models.videos import VideoCompartido
from apoderados.models import Apoderado
from notificaciones.models import Notificacion
from tests.test_apoderados import crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, RUT_PROFE
from tests.test_ver_videos import (RUT_APODERADO, RUT_MENOR, RUT_OTRO_APODERADO, RUT_OTRO_MENOR, Base,
                                   cuerpo)
from user_profesor import entregas


class VideosDeMenoresTests(Base):

    def setUp(self):
        super().setUp()
        self.apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR)
        self.menor = self.vinculo.alumno
        self.compartir(self.menor)

    # --- quién entra ---
    def como_menor(self):
        entrar(self.client, self.menor.user, alumno_id=self.menor.id_alumno)

    def como_apoderado(self, apoderado=None):
        apoderado = apoderado or self.apoderado
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)

    # --- lo que hace cada uno ---
    def lista_menor(self):
        return self.client.get(reverse('videos_alumno')).json()

    def ver_menor(self):
        return self.client.get(reverse('ver_video', args=[self.video]))

    def habilitar(self, habilitar='1', vinculo=None, video=None):
        return self.client.post(reverse('apoderado_habilitar_video',
                                        args=[(vinculo or self.vinculo).pk, video or self.video]), {'habilitar': habilitar})

    def test_el_menor_no_ve_lo_que_su_apoderado_no_reviso(self):
        self.como_menor()
        datos = self.lista_menor()
        self.assertEqual((datos['videos'], datos['por_revisar']), ([], 1))
        self.assertEqual(self.ver_menor().status_code, 404)  # ni con el enlace directo

    def test_el_apoderado_lo_ve_para_revisarlo_y_lo_habilita(self):
        self.como_apoderado()
        lista = self.client.get(reverse('apoderado_videos_estudiante', args=[self.vinculo.pk])).json()['videos']
        self.assertEqual([(v['titulo'], v['habilitado']) for v in lista], [('Factorización', False)])
        respuesta = self.client.get(reverse('apoderado_ver_video', args=[self.vinculo.pk, self.video]))
        self.assertEqual(cuerpo(respuesta), self.contenido)  # lo revisa antes de habilitarlo
        self.assertEqual(self.habilitar().json(), {'success': True, 'habilitado': True})
        self.como_menor()
        datos = self.lista_menor()
        self.assertEqual(([v['titulo'] for v in datos['videos']], datos['por_revisar']), (['Factorización'], 0))
        self.assertEqual(cuerpo(self.ver_menor()), self.contenido)

    def test_el_apoderado_puede_quitar_la_habilitacion(self):
        self.como_apoderado()
        self.habilitar()
        self.assertEqual(self.habilitar('0').json(), {'success': True, 'habilitado': False})
        self.como_menor()
        self.assertEqual(self.ver_menor().status_code, 404)

    def test_solo_su_apoderado_y_solo_videos_compartidos_y_vigentes(self):
        otro = crear_apoderado(RUT_OTRO_APODERADO, Apoderado.VERIFICADO)
        ajeno = crear_menor_vinculado(otro, rut=RUT_OTRO_MENOR)
        self.como_apoderado(otro)
        self.assertEqual(self.habilitar().status_code, 404)  # no es su estudiante
        self.assertEqual(self.habilitar(vinculo=ajeno).status_code, 404)  # su estudiante no tiene ese video
        self.como_apoderado()
        self.assertEqual(self.habilitar(video=self.subir('No compartido')).status_code, 404)
        self.assertEqual(self.habilitar(video='no-es-id').status_code, 404)
        self.menor.paquetes.update(fecha_fin=timezone.now() - timedelta(minutes=1))  # paquete vencido
        self.assertEqual(self.habilitar().status_code, 404)
        self.assertFalse(VideoCompartido.objects.filter(habilitado_menor__isnull=False).exists())

    def test_habilitar_es_solo_por_post_y_con_sesion_de_apoderado(self):
        self.como_apoderado()
        url = reverse('apoderado_habilitar_video', args=[self.vinculo.pk, self.video])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.como_menor()  # el menor no se habilita a sí mismo
        self.assertEqual(self.habilitar().status_code, 302)
        self.assertFalse(VideoCompartido.objects.filter(habilitado_menor__isnull=False).exists())

    def test_la_pagina_del_apoderado_trae_el_boton_para_habilitar(self):
        self.como_apoderado()
        pagina = self.client.get(reverse('apoderado_clases_estudiante', args=[self.vinculo.pk])).content.decode()
        self.assertIn(reverse('apoderado_habilitar_video', args=[self.vinculo.pk, 'VIDEO_ID']), pagina)

    def test_un_adulto_no_necesita_habilitacion(self):
        self.compartir(self.ana)
        self.entrar(RUT_ANA)
        self.assertEqual(self.client.get(reverse('videos_alumno')).json()['por_revisar'], 0)
        self.assertEqual(self.client.get(reverse('ver_video', args=[self.video])).status_code, 200)


class AvisoAlApoderadoTests(Base):

    def setUp(self):
        super().setUp()
        self.apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR)
        self.entrar(RUT_PROFE)

    def paquete_con_videos(self, alumno):
        paquete = self.compartir(alumno)
        paquete.videos_compartidos.all().delete()  # el paquete, sin videos todavía: los comparte el profesor
        return paquete

    def test_al_compartir_con_un_menor_se_avisa_a_su_apoderado(self):
        paquete = self.paquete_con_videos(self.vinculo.alumno)
        with self.captureOnCommitCallbacks(execute=True):
            entregas.compartir(self.profe.id_profesor, paquete.pk, self.video)
        [campanita] = Notificacion.objects.filter(usuario=self.apoderado.user)
        self.assertIn('revísalo y habilítalo', campanita.texto)
        self.assertEqual(campanita.enlace, reverse('apoderado_clases_estudiante', args=[self.vinculo.pk]))
        [correo] = mail.outbox
        self.assertEqual(correo.to, [self.apoderado.user.email])
        self.assertIn(self.vinculo.alumno.user.first_name, correo.body)

    def test_con_un_adulto_no_se_avisa_a_nadie(self):
        paquete = self.paquete_con_videos(self.ana)
        with self.captureOnCommitCallbacks(execute=True):
            entregas.compartir(self.profe.id_profesor, paquete.pk, self.video)
        self.assertEqual((Notificacion.objects.filter(usuario=self.apoderado.user).count(), len(mail.outbox)), (0, 0))
