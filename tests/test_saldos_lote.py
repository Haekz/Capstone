"""Saldos de varios profesores a la vez (user_profesor/saldos.py).

Las finanzas del admin suman el saldo de todos los profesores. Antes eran 3 consultas por
profesor; ahora son 3 en total, y cada profesor debe quedar solo con su dinero.
"""

from alumnos import paquetes
from alumnos.models import Inscripcion, SolicitudRetiro
from tests.test_filtros_clases import crear_sesion
from tests.test_metricas_admin import POR_CLASE_INTENSIVO
from tests.test_paquetes import Escenario, dar_paquete
from user_profesor.saldos import calcular_saldos, saldos_de


class SaldosEnLoteTests(Escenario):

    def setUp(self):
        # profe: dos clases dictadas del paquete intensivo y un retiro en cada estado.
        intensivo = dar_paquete(self.ana, self.profe, 'intensivo')
        for dias in (-1, -2):
            Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=intensivo,
                                       sesion=crear_sesion(self.clase, dias=dias))
        for estado, monto in ((SolicitudRetiro.APROBADO, 1000), (SolicitudRetiro.PAGADO, 2000),
                              (SolicitudRetiro.PENDIENTE, 3000), (SolicitudRetiro.RECHAZADO, 9999)):
            SolicitudRetiro.objects.create(profesor=self.profe, monto=monto, estado=estado)
        # otro: una clase dictada sin paquete (valor fijo) y un retiro en tramite.
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase_otro,
                                   sesion=crear_sesion(self.clase_otro, dias=-1))
        SolicitudRetiro.objects.create(profesor=self.otro, monto=500)
        # sin_titulo: nada.
        self.profesores = [self.profe, self.otro, self.sin_titulo]

    def test_cada_profesor_queda_con_su_dinero(self):
        ganado = 2 * POR_CLASE_INTENSIVO
        al_profe = 2 * paquetes.pago_profesor(POR_CLASE_INTENSIVO)
        saldos = saldos_de(self.profesores)
        self.assertEqual(saldos[self.profe.pk], {
            'total_ganado': ganado,
            'disponible': al_profe - 1000 - 2000 - 3000,  # el rechazado no se descuenta
            'pendiente': (ganado - al_profe) + 3000,
        })
        self.assertEqual(saldos[self.sin_titulo.pk], {'total_ganado': 0, 'disponible': 0, 'pendiente': 0})

    def test_en_lote_da_lo_mismo_que_uno_por_uno(self):
        saldos = saldos_de(self.profesores)
        for profesor in self.profesores:
            with self.subTest(profesor=profesor.pk):
                self.assertEqual(saldos[profesor.pk], calcular_saldos(profesor))

    def test_consultas_fijas_sin_importar_cuantos_profesores(self):
        profesores = list(self.profesores)  # ya cargados (con un queryset se suma 1 para leerlo)
        with self.assertNumQueries(3):  # inscripciones dictadas + videos compartidos + retiros agrupados
            saldos_de(profesores)
