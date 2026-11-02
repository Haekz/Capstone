"""El segundo apoderado pide vincularse a un menor ya registrado, con su RUT (opcion A, 02-nov). Datos ficticios."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno
from apoderados.forms import VincularEstudianteForm
from apoderados.models import Apoderado, Vinculo
from soporte.models import Ticket
from tests.test_apoderados import RUT, crear_apoderado, entrar, imagen
from tests.test_apoderados_segundo_apoderado import RUT_SEGUNDO, vincular_segundo
from tests.test_apoderados_vinculos import CLAVE_NINO, RUT_NINO, crear_menor_vinculado, hace_anios

User = get_user_model()
RUT_ADULTO, RUT_INACTIVO, RUT_INEXISTENTE = '44444444-4', '55555555-5', '22222222-2'


def datos_vinculo(**cambios):
    datos = {'rut': RUT_NINO, 'parentesco': 'padre', 'documento': imagen('certificado.jpg'), 'acepta_declaracion': 'on'}
    datos.update(cambios)
    return datos


def crear_alumno(rut, anios, activo=True):
    user = User.objects.create_user(rut, rut=rut, password=CLAVE_NINO, first_name=f'Alumno {rut}',
                                    fecha_nacimiento=hace_anios(anios), is_active=activo)
    return Alumno.objects.create(user=user, nivel_educacion='basica')


class VincularEstudianteTests(TestCase):

    def setUp(self):
        self.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo_madre = crear_menor_vinculado(self.madre)  # su primer vinculo: ella creo la cuenta
        self.alumno = self.vinculo_madre.alumno
        self.nombre_menor = self.alumno.user.first_name
        self.padre = crear_apoderado(RUT_SEGUNDO, Apoderado.VERIFICADO)
        entrar(self.client, self.padre.user, apoderado_id=self.padre.id_apoderado)
        self.url = reverse('apoderado_vincular_estudiante')

    def solicitar(self, **cambios):
        return self.client.post(self.url, datos_vinculo(**cambios))

    def vinculo_del_padre(self):
        return Vinculo.objects.get(apoderado=self.padre, alumno=self.alumno)

    # --- la solicitud ---

    def test_crea_un_vinculo_pendiente_con_documento_y_ticket_para_soporte(self):
        self.assertRedirects(self.solicitar(), reverse('portal_apoderado'))
        vinculo = self.vinculo_del_padre()
        self.assertEqual((vinculo.estado, vinculo.parentesco, vinculo.por_rut), (Vinculo.PENDIENTE, 'padre', True))
        self.assertTrue(vinculo.documentos_completos)
        self.assertEqual(vinculo.tickets.filter(categoria=Ticket.APODERADOS, estado=Ticket.ABIERTO).count(), 1)

    def test_el_primer_vinculo_no_se_toca(self):
        self.solicitar()
        self.vinculo_madre.refresh_from_db()
        self.assertEqual(self.vinculo_madre.estado, Vinculo.VERIFICADO)

    def test_encuentra_al_menor_escriba_el_rut_como_lo_escriba(self):
        self.assertRedirects(self.solicitar(rut='11.111.111-1'), reverse('portal_apoderado'))
        otro = crear_alumno('22.222.222-2', 10)  # guardado con puntos
        self.assertRedirects(self.solicitar(rut='22222222-2'), reverse('portal_apoderado'))
        self.assertTrue(Vinculo.objects.filter(apoderado=self.padre, alumno=otro).exists())

    def test_mientras_esta_pendiente_no_puede_actuar_por_el_menor(self):
        self.solicitar()
        vinculo = self.vinculo_del_padre()
        self.assertFalse(vinculo.autoriza(self.alumno))
        self.assertEqual(self.client.get(reverse('apoderado_clases_estudiante', args=[vinculo.pk])).status_code, 404)

    # --- privacidad: escribir un RUT no debe revelar nada ---

    def test_todo_fallo_de_la_busqueda_responde_lo_mismo(self):
        crear_alumno(RUT_ADULTO, 30)
        crear_alumno(RUT_INACTIVO, 10, activo=False)
        for rut in (RUT_INEXISTENTE, RUT_ADULTO, RUT_INACTIVO):
            with self.subTest(rut=rut):
                respuesta = self.solicitar(rut=rut)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, VincularEstudianteForm.SIN_COINCIDENCIA)
                self.assertNotContains(respuesta, f'Alumno {rut}')
        self.assertFalse(Vinculo.objects.filter(apoderado=self.padre).exists())

    def test_no_muestra_el_nombre_del_menor_hasta_que_soporte_verifique(self):
        respuesta = self.client.post(self.url, datos_vinculo(), follow=True)
        self.assertNotContains(respuesta, self.nombre_menor)  # ni en el aviso ni en el portal
        self.assertContains(respuesta, '<strong>Estudiante</strong>')
        self.assertContains(respuesta, f'RUT {RUT_NINO}')  # el RUT lo escribio ella
        vinculo = self.vinculo_del_padre()
        self.assertNotContains(self.client.get(reverse('apoderado_revocar_vinculo', args=[vinculo.pk])), self.nombre_menor)
        Vinculo.objects.filter(pk=vinculo.pk).update(estado=Vinculo.VERIFICADO)
        self.assertContains(self.client.get(reverse('portal_apoderado')), self.nombre_menor)

    def test_un_rechazado_tampoco_ve_el_nombre(self):
        self.solicitar()
        Vinculo.objects.filter(apoderado=self.padre).update(estado=Vinculo.RECHAZADO)
        self.assertNotContains(self.client.get(reverse('portal_apoderado')), self.nombre_menor)

    # --- validaciones y permisos ---

    def test_rut_con_formato_invalido(self):
        respuesta = self.solicitar(rut='abc')
        self.assertContains(respuesta, 'no es válido')
        self.assertFalse(Vinculo.objects.filter(apoderado=self.padre).exists())

    def test_exige_documento_y_declaracion(self):
        for faltante in ('documento', 'acepta_declaracion'):
            datos = datos_vinculo()
            del datos[faltante]
            self.client.post(self.url, datos)
        self.assertFalse(Vinculo.objects.filter(apoderado=self.padre).exists())

    def test_no_pide_dos_veces_el_mismo_vinculo(self):
        self.solicitar()
        respuesta = self.solicitar()
        self.assertContains(respuesta, 'Ya tienes un vínculo')
        self.assertEqual(Vinculo.objects.filter(apoderado=self.padre).count(), 1)

    def test_con_la_identidad_sin_verificar_no_puede(self):
        sin_verificar = crear_apoderado('66666666-6', Apoderado.REVISION_PENDIENTE)
        entrar(self.client, sin_verificar.user, apoderado_id=sin_verificar.id_apoderado)
        self.assertRedirects(self.solicitar(), reverse('portal_apoderado'))
        self.assertFalse(Vinculo.objects.filter(apoderado=sin_verificar).exists())

    def test_sin_sesion_no_entra(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(self.url).status_code, 200)

    def test_el_portal_ofrece_la_opcion_solo_a_un_apoderado_verificado(self):
        self.assertContains(self.client.get(reverse('portal_apoderado')), self.url)
        sin_verificar = crear_apoderado('66666666-6', Apoderado.REVISION_PENDIENTE)
        entrar(self.client, sin_verificar.user, apoderado_id=sin_verificar.id_apoderado)
        self.assertNotContains(self.client.get(reverse('portal_apoderado')), self.url)
