"""Retiros de profesores: quien aprueba, rechaza y paga, y estados que solo avanzan.

Aprobar no es pagar: la plata se mueve en el banco y despues el admin registra
el numero de operacion (DECISIONES_SOPORTE_Y_PAGOS.md, paso 2).
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from alumnos import paquetes
from alumnos.models import Inscripcion, SolicitudRetiro, Tutor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_PROFE, Escenario, dar_paquete
from user_profesor.views import calcular_saldos

RUT_ADMIN = '66666666-6'


def crear_admin():
    admin = get_user_model().objects.create_user(
        username=RUT_ADMIN, rut=RUT_ADMIN, password='AdminClave123!', rol='admin', first_name='Admin')
    return admin, Tutor.objects.create(user=admin)


def entrar_admin(client, admin, tutor):
    client.force_login(admin)
    sesion = client.session
    sesion['admin_id'] = tutor.id_tutor
    sesion.save()


class RetirosTests(Escenario):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin, cls.tutor = crear_admin()

    def setUp(self):
        self.retiro = SolicitudRetiro.objects.create(profesor=self.profe, monto=10000)

    def post(self, vista, **datos):
        """POST del admin sobre self.retiro; devuelve el dashboard con su mensaje."""
        entrar_admin(self.client, self.admin, self.tutor)
        respuesta = self.client.post(reverse(vista, args=[self.retiro.pk]), datos, follow=True)
        self.retiro.refresh_from_db()
        return respuesta

    def test_aprobar_registra_quien_y_cuando(self):
        self.post('aprobar_retiro')
        self.assertEqual(self.retiro.estado, SolicitudRetiro.APROBADO)
        self.assertEqual(self.retiro.resuelto_por, self.admin)
        self.assertIsNotNone(self.retiro.fecha_resolucion)

    def test_rechazar_exige_motivo(self):
        respuesta = self.post('rechazar_retiro', motivo='   ')
        self.assertEqual(self.retiro.estado, SolicitudRetiro.PENDIENTE)
        self.assertContains(respuesta, 'Escribe el motivo del rechazo')

        self.post('rechazar_retiro', motivo='La cuenta no es del profesor')
        self.assertEqual((self.retiro.estado, self.retiro.motivo_rechazo, self.retiro.resuelto_por),
                         (SolicitudRetiro.RECHAZADO, 'La cuenta no es del profesor', self.admin))

    def test_pagar_exige_aprobacion_y_numero_de_operacion(self):
        respuesta = self.post('marcar_pagado_retiro', numero_operacion='OP-1')
        self.assertEqual(self.retiro.estado, SolicitudRetiro.PENDIENTE)
        self.assertContains(respuesta, 'No se puede')

        self.post('aprobar_retiro')
        self.post('marcar_pagado_retiro', numero_operacion='  ')
        self.assertEqual(self.retiro.estado, SolicitudRetiro.APROBADO)

        self.post('marcar_pagado_retiro', numero_operacion=' OP-998 ')
        self.assertEqual((self.retiro.estado, self.retiro.numero_operacion, self.retiro.pagado_por),
                         (SolicitudRetiro.PAGADO, 'OP-998', self.admin))
        self.assertIsNotNone(self.retiro.fecha_pago)

    def test_los_estados_solo_avanzan(self):
        self.retiro.rechazar(self.admin, 'Datos incompletos')
        pagado = SolicitudRetiro.objects.create(profesor=self.profe, monto=5000)
        pagado.aprobar(self.admin)
        pagado.marcar_pagado(self.admin, 'OP-1')

        pasos_prohibidos = {
            'aprobar un rechazado': lambda: self.retiro.aprobar(self.admin),
            'pagar un rechazado': lambda: self.retiro.marcar_pagado(self.admin, 'OP-2'),
            'aprobar un pagado': lambda: pagado.aprobar(self.admin),
            'rechazar un pagado': lambda: pagado.rechazar(self.admin, 'Error'),
            'pagar dos veces': lambda: pagado.marcar_pagado(self.admin, 'OP-3'),
        }
        for nombre, paso in pasos_prohibidos.items():
            with self.subTest(nombre), self.assertRaises(ValidationError):
                paso()
        pagado.refresh_from_db()
        self.assertEqual(pagado.numero_operacion, 'OP-1')

    def test_retiro_pagado_sigue_descontando_del_saldo(self):
        """Si dejara de descontar, el profesor podria cobrar dos veces lo mismo."""
        paquete = dar_paquete(self.ana, self.profe, 'intensivo')
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=paquete,
                                   sesion=crear_sesion(self.clase, dias=-1))
        self.retiro.monto = paquetes.pago_profesor(14500)
        self.retiro.save()
        self.retiro.aprobar(self.admin)
        self.retiro.marcar_pagado(self.admin, 'OP-7')
        self.assertEqual(calcular_saldos(self.profe)['disponible'], 0)

    def test_el_profesor_ve_el_pago_y_el_motivo_del_rechazo(self):
        self.retiro.aprobar(self.admin)
        self.retiro.marcar_pagado(self.admin, 'OP-55')
        SolicitudRetiro.objects.create(profesor=self.profe, monto=2000).rechazar(self.admin, 'Cuenta de un tercero')
        self.entrar(RUT_PROFE)
        respuesta = self.client.get(reverse('panel_profesor'))
        self.assertContains(respuesta, 'Op. OP-55')
        self.assertContains(respuesta, 'Cuenta de un tercero')
        self.assertNotContains(respuesta, 'Transferido')
