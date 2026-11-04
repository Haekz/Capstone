"""Maquetas retiradas: el chat inventado del panel del profesor y el chat de la sala que no enviaba nada.

Lo que el usuario ve tiene que ser verdad: ningún mensaje con nombres de personas que no existen y ninguna promesa
de "chat privado" cuyo texto nadie recibe.
"""

from datetime import time

from django.urls import reverse

from alumnos.models import Asignatura, Clase
from tests.test_paquetes import RUT_PROFE, Escenario


class ChatsDeVerdadTests(Escenario):

    def setUp(self):
        self.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'), modalidad='online',
                                          horario=time(10, 0), profesor=self.profe)

    def test_el_panel_del_profesor_no_trae_el_chat_ni_el_estudio_simulados(self):
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'))
        self.assertEqual(r.status_code, 200)
        for simulado in ('mockMessages', 'startMockStudentLiveChat', 'toggleStreamingSession', 'Sofía Rojas',
                         'Lucas Altamirano', 'commondatastorage.googleapis.com'):
            self.assertNotContains(r, simulado)
        self.assertContains(r, reverse('sala_virtual', args=[self.clase.id_clase]))  # la sala de verdad sigue

    def test_la_sala_no_promete_un_chat_privado_que_no_envia_nada(self):
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('sala_virtual', args=[self.clase.id_clase]))
        self.assertEqual(r.status_code, 200)
        for falso in ('chat-input-text', 'sendMessage', 'privado entre el profesor'):
            self.assertNotContains(r, falso)
        self.assertContains(r, 'chat de la videollamada')
        self.assertContains(r, "'chat'")  # el de Jitsi, que sí llega a la otra persona, sigue en la barra
