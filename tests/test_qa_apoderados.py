"""Revision QA: apoderados y menores (apoderados/views.py, permisos.py, tokens.py, documentos).

Complementa tests/test_apoderados_*.py. Riesgos: un apoderado actua con el
vinculo de otro (IDOR en las rutas con id_vinculo), un documento de identidad se
abre sin el ticket o termina en 500 al rotar la clave, y enlaces alterados.
"""


from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.urls import reverse

from alumnos.models import Asignatura, Clase, Inscripcion
from apoderados.models import AccesoDocumento, Apoderado, CompraApoderado, Documento, Vinculo
from apoderados.tokens import invitacion_vigente, user_id_de_uid
from soporte.models import Ticket
from soporte.tickets import abrir_ticket
from tests.test_apoderados import RUT, adjuntar, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_vinculos import CLAVE_NINO, crear_menor_vinculado
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import dar_paquete

# Rutas del apoderado que reciben un id_vinculo: (nombre, metodo, argumentos extra).
RUTAS_CON_VINCULO = [
    ('apoderado_clases_estudiante', 'get', []),
    ('apoderado_clave_estudiante', 'get', []),
    ('apoderado_clave_estudiante', 'post', []),
    ('apoderado_subir_documento_vinculo', 'get', []),
    ('apoderado_revocar_vinculo', 'get', []),
    ('apoderado_revocar_vinculo', 'post', []),
    ('apoderado_comprar_paquete', 'post', []),
    ('apoderado_reservar_clase', 'post', []),
    ('apoderado_cancelar_clase', 'post', ['inscripcion']),
    ('apoderado_reprogramar_clase', 'post', ['inscripcion']),
]


class VinculoAjenoTests(TestCase):
    """Riesgo: IDOR. La madre de un menor usa el id del vinculo de otro apoderado con otro menor."""

    @classmethod
    def setUpTestData(cls):
        cls.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.otro = crear_apoderado('55555555-5', Apoderado.VERIFICADO)
        crear_menor_vinculado(cls.madre)
        cls.vinculo_ajeno = crear_menor_vinculado(cls.otro, rut='19000000-1')
        profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Física'), modalidad='online',
                                     profesor=profesor)
        paquete = dar_paquete(cls.vinculo_ajeno.alumno, profesor)
        CompraApoderado.objects.create(paquete=paquete, apoderado=cls.otro, vinculo=cls.vinculo_ajeno)
        cls.sesion = crear_sesion(clase, dias=3)
        cls.reserva = Inscripcion.objects.create(alumno=cls.vinculo_ajeno.alumno, clase=clase, sesion=cls.sesion,
                                                 paquete=paquete, estado=Inscripcion.ESTADO_CONFIRMADA)

    def setUp(self):
        entrar(self.client, self.madre.user, apoderado_id=self.madre.id_apoderado)

    def test_ninguna_ruta_con_id_vinculo_acepta_el_vinculo_de_otro_apoderado(self):
        for nombre, metodo, extra in RUTAS_CON_VINCULO:
            with self.subTest(ruta=nombre, metodo=metodo):
                args = [self.vinculo_ajeno.pk, *(self.reserva.pk for _ in extra)]
                datos = {'id_sesion': self.sesion.pk, 'plan': 'progreso', 'motivo': 'qa',
                         'new_password1': 'Clave-Nueva-QA-2026', 'new_password2': 'Clave-Nueva-QA-2026'}
                r = getattr(self.client, metodo)(reverse(nombre, args=args), datos if metodo == 'post' else None)
                self.assertEqual(r.status_code, 404)
        self.reserva.refresh_from_db()
        self.vinculo_ajeno.refresh_from_db()
        self.assertEqual(self.reserva.estado, Inscripcion.ESTADO_CONFIRMADA)
        self.assertEqual(self.vinculo_ajeno.estado, Vinculo.VERIFICADO)
        self.vinculo_ajeno.alumno.user.refresh_from_db()
        self.assertTrue(self.vinculo_ajeno.alumno.user.check_password(CLAVE_NINO))
        self.assertFalse(CompraApoderado.objects.filter(apoderado=self.madre).exists())


class EntradasAlteradasTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.madre)

    def test_id_de_sesion_no_numerico_avisa_y_no_reserva(self):
        """Riesgo: un id_sesion manipulado ('abc') termina en 500 en vez de un aviso."""
        entrar(self.client, self.madre.user, apoderado_id=self.madre.id_apoderado)
        r = self.client.post(reverse('apoderado_reservar_clase', args=[self.vinculo.pk]), {'id_sesion': 'abc'},
                             follow=True)
        self.assertContains(r, 'Elige una sesión válida.')
        self.assertFalse(Inscripcion.objects.exists())

    def test_enlaces_alterados_no_identifican_a_nadie(self):
        """Riesgo: un uid o una invitacion falsificada abre la cuenta o la invitacion de otro."""
        for uid in ('***', 'bm8tbnVtZXJv', ''):  # no es base64 / 'no-numero' / vacio
            with self.subTest(uid=uid):
                self.assertIsNone(user_id_de_uid(uid))
        self.assertIsNone(invitacion_vigente('firma-falsa'))
        self.assertIsNone(invitacion_vigente(''))

    def test_cambiar_la_clave_propia_sin_necesidad_vuelve_al_portal(self):
        """Riesgo: la pantalla 'define tu contrasena' se usa para cambiarla sin pedir la actual."""
        menor = self.vinculo.alumno
        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        self.assertRedirects(self.client.get(reverse('nueva_clave_estudiante')), reverse('alumno_pag1'),
                             fetch_redirect_response=False)


class DocumentoQATests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10101010-1', Ticket.APODERADOS)
        self.apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        abrir_ticket(Ticket.APODERADOS, apoderado=self.apoderado)
        self.documento = adjuntar(Documento.CARNET_FRENTE, apoderado=self.apoderado)
        self.url = reverse('apoderado_documento', args=[self.documento.pk])

    def test_otro_agente_de_la_misma_area_sin_el_ticket_no_lo_ve(self):
        """Riesgo: IDOR entre agentes. Estar habilitado en la categoria no basta: hace falta el ticket."""
        otro = crear_agente('20202020-2', Ticket.APODERADOS)
        entrar_soporte(self.client, otro)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertFalse(AccesoDocumento.objects.exists())

    def test_con_la_clave_rotada_da_404_y_no_queda_registro(self):
        """Riesgo: cambiar DOCUMENTOS_CLAVE deja los documentos viejos en 500 (InvalidToken sin capturar)."""
        entrar_soporte(self.client, self.agente)
        with override_settings(DOCUMENTOS_CLAVE=Fernet.generate_key().decode()):
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)
        self.assertFalse(AccesoDocumento.objects.exists())
