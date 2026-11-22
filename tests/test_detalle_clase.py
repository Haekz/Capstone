"""Pagina de una clase reservada (21-nov): la ven el alumno, su apoderado y el profesor, cada uno con lo suyo. Datos ficticios.

Es de solo lectura. Lo que muestra tiene que coincidir con lo que de verdad permite la sala virtual y los flujos de
cambiar o cancelar, que ya existen y tienen sus propias pruebas.
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Asignatura, Clase, Inscripcion, Profesor
from alumnos.services import InscripcionService
from apoderados.forms import VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, CompraApoderado, Vinculo
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_cancelar_4_horas import EN_2_HORAS, EN_3_DIAS, EN_5_HORAS
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, RUT_BETO, RUT_OTRO, RUT_PROFE, Escenario, dar_paquete


class DetalleClaseAlumnoYProfesorTests(Escenario):

    def setUp(self):
        for persona, apellido in ((self.ana, 'Soto'), (self.profe, 'Rojas')):
            persona.user.last_name = apellido
            persona.user.save()
        self.ana.user.email, self.ana.user.telefono = 'ana@lbwus.cl', '922222222'
        self.ana.user.save()
        dar_paquete(self.ana, self.profe)

    def reservar(self, dias=EN_3_DIAS):
        return InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=dias).pk)

    def ver(self, inscripcion, rut):
        self.entrar(rut)
        return self.client.get(reverse('detalle_clase', args=[inscripcion.pk]))

    def test_el_alumno_ve_su_clase_con_el_profesional_y_las_dos_acciones(self):
        inscripcion = self.reservar()
        respuesta = self.ver(inscripcion, RUT_ANA)
        self.assertContains(respuesta, 'Algebra')
        self.assertContains(respuesta, 'Profe Rojas')
        self.assertContains(respuesta, '(hora de Chile)')
        self.assertContains(respuesta, f'href="{reverse("sala_virtual", args=[self.clase.id_clase])}"')
        self.assertContains(respuesta, 'Ir a la clase')
        self.assertContains(respuesta, 'Necesito cambiar el horario')
        self.assertContains(respuesta, 'sin costo hasta 4 horas antes')
        self.assertContains(respuesta, f'href="{reverse("alumno_pag1")}"')

    def test_el_profesor_ve_nombre_y_apellido_del_alumno_y_cancela_hasta_12_horas_antes(self):
        inscripcion = self.reservar()
        respuesta = self.ver(inscripcion, RUT_PROFE)
        self.assertContains(respuesta, 'Ana Soto')
        self.assertContains(respuesta, 'Ir a la clase')
        self.assertContains(respuesta, 'hasta 12 horas antes')
        self.assertContains(respuesta, f'href="{reverse("panel_profesor")}"')

    def test_nadie_ve_rut_correo_ni_telefono_del_otro(self):
        inscripcion = self.reservar()
        privados = {RUT_ANA: self.profe.user, RUT_PROFE: self.ana.user}
        for rut, ajeno in privados.items():
            html = self.ver(inscripcion, rut).content.decode()
            for dato in (ajeno.rut, ajeno.email, ajeno.telefono):
                with self.subTest(rut=rut, dato=dato):
                    self.assertTrue(dato)  # existe: si estuviera vacio la prueba no probaria nada
                    self.assertNotIn(dato, html)

    def test_las_reglas_son_4_horas_para_el_alumno_y_12_para_el_profesor(self):
        inscripcion = self.reservar(EN_5_HORAS)  # faltan 5 h: el alumno aun cambia sin costo, el profesor ya no cancela
        alumno = self.ver(inscripcion, RUT_ANA)
        self.assertContains(alumno, 'sin costo hasta 4 horas antes')
        self.assertContains(alumno, 'Cambiar el horario')
        profesor = self.ver(inscripcion, RUT_PROFE)
        self.assertContains(profesor, 'menos de 12 horas')
        self.assertNotContains(profesor, 'Ir a mi agenda')

    def test_con_menos_de_4_horas_ya_no_se_cambia_el_horario_solo_se_cancela_y_se_cobra(self):
        respuesta = self.ver(self.reservar(EN_2_HORAS), RUT_ANA)
        self.assertContains(respuesta, 'ya no se puede cambiar el horario')
        self.assertContains(respuesta, 'el profesor la cobra')
        self.assertContains(respuesta, 'Cancelar la clase')
        self.assertNotContains(respuesta, 'Cambiar el horario')

    def test_una_clase_cancelada_no_ofrece_entrar_ni_cambiar(self):
        inscripcion = self.reservar()
        InscripcionService.cancelar_inscripcion(self.ana, inscripcion.pk)
        for rut in (RUT_ANA, RUT_PROFE):
            respuesta = self.ver(inscripcion, rut)
            with self.subTest(rut=rut):
                self.assertContains(respuesta, 'Cancelada')
                self.assertNotContains(respuesta, 'Ir a la clase')
                self.assertNotContains(respuesta, 'Necesito cambiar el horario')

    def test_quien_no_tiene_relacion_con_la_clase_recibe_404(self):
        inscripcion = self.reservar()
        for rut in (RUT_BETO, RUT_OTRO):  # otro alumno y otro profesor
            self.assertEqual(self.ver(inscripcion, rut).status_code, 404, rut)

    def test_una_reserva_que_no_existe_o_sin_sesion_recibe_404(self):
        sin_sesion = Inscripcion.objects.create(alumno=self.ana, clase=self.clase,
                                                estado=Inscripcion.ESTADO_CONFIRMADA)
        self.entrar(RUT_ANA)
        for pk in (sin_sesion.pk, 999999):
            self.assertEqual(self.client.get(reverse('detalle_clase', args=[pk])).status_code, 404)

    def test_el_anonimo_entra_y_vuelve_a_la_clase(self):
        ruta = reverse('detalle_clase', args=[self.reservar().pk])
        respuesta = self.client.get(ruta)
        self.assertRedirects(respuesta, f"{reverse('login')}?next={ruta.replace('/', '%2F')}", fetch_redirect_response=False)
        self.assertContains(self.client.get(f"{reverse('login')}?next={ruta}"), f'name="next" value="{ruta}"')

    def test_el_profesor_sin_titulo_validado_no_ve_el_boton_igual_que_la_sala(self):
        inscripcion = self.reservar()
        Profesor.objects.filter(pk=self.profe.pk).update(titulo_estado=Profesor.TITULO_EN_REVISION)
        self.assertNotContains(self.ver(inscripcion, RUT_PROFE), 'Ir a la clase')
        self.assertEqual(self.client.get(reverse('sala_virtual', args=[self.clase.id_clase])).status_code, 403)

    def test_el_boton_de_entrar_coincide_con_lo_que_permite_la_sala(self):
        inscripcion = self.reservar()
        for rut in (RUT_ANA, RUT_PROFE):
            self.assertContains(self.ver(inscripcion, rut), 'Ir a la clase')
            self.assertEqual(self.client.get(reverse('sala_virtual', args=[self.clase.id_clase])).status_code, 200)

    def test_un_nombre_con_html_se_muestra_escapado(self):
        self.profe.user.last_name = '<b>Rojas</b>'
        self.profe.user.save()
        html = self.ver(self.reservar(), RUT_ANA).content.decode()
        self.assertIn('&lt;b&gt;Rojas&lt;/b&gt;', html)
        self.assertNotIn('<b>Rojas', html)


class DetalleClaseApoderadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', profesor=cls.profesor)
        cls.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.madre)
        cls.menor = cls.vinculo.alumno
        cls.menor.user.last_name = 'Pérez'
        cls.menor.user.save()
        paquete = dar_paquete(cls.menor, cls.profesor)
        CompraApoderado.objects.create(paquete=paquete, apoderado=cls.madre, vinculo=cls.vinculo)
        cls.inscripcion = InscripcionService.inscribir_alumno_en_sesion(
            cls.menor, crear_sesion(cls.clase, dias=3).pk, vinculo=cls.vinculo)
        cls.url = reverse('detalle_clase', args=[cls.inscripcion.pk])

    def test_el_apoderado_ve_al_estudiante_y_cambia_desde_su_pantalla_pero_no_entra_a_la_sala(self):
        entrar(self.client, self.madre.user, apoderado_id=self.madre.id_apoderado)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, self.menor.user.get_full_name())
        self.assertContains(respuesta, 'Estudiante')
        self.assertContains(respuesta, 'entra a la clase desde su propia cuenta')
        self.assertNotContains(respuesta, 'Ir a la clase')
        self.assertContains(respuesta, f'href="{reverse("apoderado_clases_estudiante", args=[self.vinculo.pk])}"')
        # y la sala, en efecto, no lo deja entrar: el boton no existe porque no serviria
        self.assertEqual(self.client.get(reverse('sala_virtual', args=[self.clase.id_clase])).status_code, 403)

    def test_el_menor_entra_a_la_clase_pero_el_cambio_lo_hace_su_apoderado(self):
        entrar(self.client, self.menor.user, alumno_id=self.menor.id_alumno)
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'Ir a la clase')
        self.assertContains(respuesta, 'Tu apoderado puede cambiar el horario')
        self.assertNotContains(respuesta, 'Cambiar el horario')
        self.assertEqual(self.client.get(reverse('sala_virtual', args=[self.clase.id_clase])).status_code, 200)

    def test_un_vinculo_que_ya_no_autoriza_recibe_404(self):
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.PENDIENTE)
        entrar(self.client, self.madre.user, apoderado_id=self.madre.id_apoderado)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_otro_apoderado_sin_vinculo_recibe_404(self):
        ajeno = crear_apoderado('66666666-6', Apoderado.VERIFICADO)
        entrar(self.client, ajeno.user, apoderado_id=ajeno.id_apoderado)
        self.assertEqual(self.client.get(self.url).status_code, 404)
