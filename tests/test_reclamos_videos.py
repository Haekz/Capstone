"""Reclamos por un video (fase 5b): "Reportar este video" abre el formulario de tickets de siempre, ya rellenado.

Politica (seccion 12): el alumno reclama con un ticket (no corresponde a la materia, o es inapropiado). Igual que
"Reportar problema con este pago": el video llega por la URL y se usa solo si se le compartio al usuario o a su
estudiante; si no, solo se elige el tema (sin datos de un video ajeno). El menor no abre tickets: lo hace su
apoderado (D18), asi que a el no se le muestra el enlace.
"""

from django.urls import reverse

from apoderados.models import Apoderado
from soporte.models import Ticket
from tests.test_apoderados import crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, RUT_BETO
from tests.test_ver_videos import RUT_APODERADO, RUT_MENOR, Base


class ReclamosVideosTests(Base):

    def formulario(self, video):
        return self.client.get(reverse('nuevo_ticket'), {'video': video}).context['form'].initial

    def test_el_alumno_lo_reporta_con_el_formulario_rellenado(self):
        self.compartir(self.ana)
        self.entrar(RUT_ANA)
        inicial = self.formulario(self.video)
        self.assertEqual((inicial['categoria'], inicial['titulo']), (Ticket.VIDEOS, 'Problema con un video de apoyo'))
        self.assertIn(self.video, inicial['descripcion'])
        self.assertIn(self.profe.nombre, inicial['descripcion'])
        self.client.post(reverse('nuevo_ticket'), {'categoria': Ticket.VIDEOS, 'titulo': inicial['titulo'],
                                                   'descripcion': inicial['descripcion'] + 'No es de Álgebra.'})
        [ticket] = Ticket.objects.filter(categoria=Ticket.VIDEOS, autor__username=RUT_ANA)
        self.assertEqual(ticket.estado, Ticket.ABIERTO)

    def test_un_video_ajeno_solo_elige_el_tema(self):
        self.compartir(self.ana)
        self.entrar(RUT_BETO)
        self.assertEqual(self.formulario(self.video), {'categoria': Ticket.VIDEOS})

    def test_el_panel_del_alumno_adulto_trae_el_enlace(self):
        self.compartir(self.ana)
        self.entrar(RUT_ANA)
        self.assertContains(self.client.get(reverse('alumno_pag1')), f"{reverse('nuevo_ticket')}?video=")

    def test_el_apoderado_reporta_por_su_estudiante(self):
        apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        vinculo = crear_menor_vinculado(apoderado, rut=RUT_MENOR)
        self.compartir(vinculo.alumno)
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)
        self.assertEqual(self.formulario(self.video)['estudiante'], vinculo.alumno.pk)
        pagina = self.client.get(reverse('apoderado_clases_estudiante', args=[vinculo.pk]))
        self.assertContains(pagina, f"{reverse('nuevo_ticket')}?video=")

    def test_al_menor_no_se_le_muestra_el_enlace(self):
        apoderado = crear_apoderado(RUT_APODERADO, Apoderado.VERIFICADO)
        menor = crear_menor_vinculado(apoderado, rut=RUT_MENOR).alumno
        self.compartir(menor)
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        self.assertNotContains(self.client.get(reverse('alumno_pag1')), f"{reverse('nuevo_ticket')}?video=")
