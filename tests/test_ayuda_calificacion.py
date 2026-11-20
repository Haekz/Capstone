"""Ayuda al calificar: telefonos segun quien es la persona y cuadro de estrellas al entrar al portal.

Menor: 133, 147 y 149. Mujer adulta: 133, 1455 y 149. Hombre adulto: 133 y 149. Con 1 o 2 estrellas se muestran
al calificar; si quien califica es menor, ademas le llega un correo a su apoderado con los mismos telefonos.
"""

from types import SimpleNamespace

from django.core import mail
from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.ayuda import lineas_para
from alumnos.models import Genero
from alumnos.roles import ALUMNO
from apoderados.models import Apoderado
from resenas.consultas import pendiente_de_calificar
from tests.test_apoderados import crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado, hace_anios
from tests.test_progreso_alumno import crear_alumno
from tests.test_resenas import BaseResenas, entrar

AYUDA = '¿Necesitas ayuda ahora?'


def persona(anios, genero):
    return SimpleNamespace(fecha_nacimiento=hace_anios(anios),
                           genero=SimpleNamespace(descripcion=genero) if genero else None)


class LineasParaTests(SimpleTestCase):

    def numeros(self, user):
        return [linea.numero for linea in lineas_para(user)]

    def test_menor(self):
        self.assertEqual(self.numeros(persona(10, 'Femenino')), ['133', '147', '149'])
        self.assertEqual(self.numeros(persona(17, 'Masculino')), ['133', '147', '149'])

    def test_mujer_adulta(self):
        self.assertEqual(self.numeros(persona(30, 'Femenino')), ['133', '1455', '149'])

    def test_hombre_adulto(self):
        self.assertEqual(self.numeros(persona(30, 'Masculino')), ['133', '149'])

    def test_otro_o_sin_decir_ve_las_tres_de_adultos(self):
        for genero in ('Otro', 'Prefiero no decir', None):
            with self.subTest(genero=genero):
                self.assertEqual(self.numeros(persona(30, genero)), ['133', '149', '1455'])


class CalificarConAyudaTests(BaseResenas):

    def calificar(self, alumno, inscripcion, puntaje):
        entrar(self.client, alumno, ALUMNO)
        return self.client.post(reverse('resena_calificar', args=[inscripcion.id_inscripcion]),
                                {'puntaje': puntaje}, follow=True)

    def con_genero(self, alumno, descripcion):
        alumno.user.genero = Genero.objects.get_or_create(descripcion=descripcion)[0]
        alumno.user.save(update_fields=['genero'])

    def test_mujer_adulta_con_nota_baja_ve_133_1455_y_149(self):
        self.con_genero(self.ana, 'Femenino')
        respuesta = self.calificar(self.ana, self.insc_paquete, 1)
        self.assertContains(respuesta, AYUDA)
        for numero in ('133', '1455', '149'):
            self.assertContains(respuesta, f'tel:{numero}')
        self.assertContains(respuesta, '+56 9 9700 7000')
        self.assertNotContains(respuesta, 'tel:147')

    def test_hombre_adulto_con_nota_baja_ve_133_y_149_sin_1455(self):
        self.con_genero(self.ana, 'Masculino')
        respuesta = self.calificar(self.ana, self.insc_paquete, 2)
        self.assertContains(respuesta, 'tel:133')
        self.assertContains(respuesta, 'tel:149')
        self.assertNotContains(respuesta, 'tel:1455')
        self.assertNotContains(respuesta, 'tel:147')

    def test_con_3_o_mas_estrellas_no_se_muestra_ayuda(self):
        for puntaje, inscripcion in ((3, self.insc_paquete), (5, self.insc_suelta)):
            with self.subTest(puntaje=puntaje):
                self.assertNotContains(self.calificar(self.ana, inscripcion, puntaje), AYUDA)

    def test_el_adulto_no_dispara_correo_a_ningun_apoderado(self):
        self.calificar(self.ana, self.insc_paquete, 1)
        self.assertEqual(mail.outbox, [])

    def test_menor_con_nota_baja_ve_147_y_avisa_al_apoderado_con_los_telefonos(self):
        apoderado = crear_apoderado('55555555-5', Apoderado.VERIFICADO)
        menor = crear_menor_vinculado(apoderado, rut='66666666-6').alumno
        inscripcion = self.inscribir(menor, dias=-3)
        respuesta = self.calificar(menor, inscripcion, 2)
        for numero in ('133', '147', '149'):
            self.assertContains(respuesta, f'tel:{numero}')
        self.assertNotContains(respuesta, 'tel:1455')

        self.assertEqual([m.to for m in mail.outbox], [[apoderado.user.email]])
        cuerpo = mail.outbox[0].body
        for esperado in ('urgente', 'ticket', '133', '147', '149'):
            self.assertIn(esperado, cuerpo)


class CuadroDeEstrellasTests(BaseResenas):
    """El portal ofrece calificar la ultima clase completada que aun no tiene reseña."""

    def abrir_portal(self, alumno):
        entrar(self.client, alumno, ALUMNO)
        return self.client.get(reverse('alumno_pag1'))

    def url(self, inscripcion):
        return reverse('resena_calificar', args=[inscripcion.id_inscripcion])

    def test_aparece_con_la_ultima_clase_completada_sin_calificar(self):
        respuesta = self.abrir_portal(self.ana)
        self.assertContains(respuesta, 'id="dialogo-calificar"')
        self.assertContains(respuesta, f'action="{self.url(self.insc_paquete)}"')

    def test_la_resena_del_paquete_cubre_sus_otras_clases_y_pasa_a_la_siguiente(self):
        self.inscribir(self.ana, dias=-1, paquete=self.paquete)  # otra clase completada del mismo paquete
        self.resena(self.insc_paquete)
        respuesta = self.abrir_portal(self.ana)
        self.assertContains(respuesta, f'action="{self.url(self.insc_suelta)}"')  # la suelta no tiene reseña

    def test_no_aparece_si_todo_esta_calificado(self):
        self.resena(self.insc_paquete)
        self.resena(self.insc_suelta)
        self.assertNotContains(self.abrir_portal(self.ana), 'id="dialogo-calificar"')

    def test_no_aparece_sin_clases_completadas_ni_con_clases_futuras(self):
        nueva = crear_alumno('44444444-4', 'Caro', Genero.objects.first())
        self.inscribir(nueva, dias=2)
        self.assertNotContains(self.abrir_portal(nueva), 'id="dialogo-calificar"')
        self.assertIsNone(pendiente_de_calificar(nueva))

    def test_cada_alumno_ve_solo_lo_suyo(self):
        respuesta = self.abrir_portal(self.bea)
        self.assertContains(respuesta, f'action="{self.url(self.insc_bea)}"')
        self.assertNotContains(respuesta, self.url(self.insc_paquete))
