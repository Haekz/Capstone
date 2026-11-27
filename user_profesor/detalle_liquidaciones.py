"""Detalle de liquidaciones del profesor: cada clase dictada y cada video compartido que suma a su saldo, con lo que pago el
alumno, la comision de LBWUS y lo que le queda al profesor.

Usa las mismas consultas y la misma cuenta que saldos.py (pagables(), videos_con_valor, paquetes.comision y pago_profesor), asi
que la suma del abono es exactamente lo que el saldo llama «lo que corresponde al profesor»: el detalle no puede contradecirlo.
No hay tabla de desglose (decidido, docs/CONCILIACION_Y_TRANSBANK_7_6.md): comision y abono se calculan cada vez.
Los retiros no son por operacion: van en el historial de retiros.
"""

from dataclasses import dataclass
from datetime import datetime

from alumnos import paquetes
from alumnos.models import Inscripcion, VideoCompartido

from .saldos import videos_con_valor

MAXIMO = 50  # las mas recientes; el total se informa aparte para no inflar la pagina


@dataclass(frozen=True)
class Operacion:
    fecha: datetime
    alumno: str
    concepto: str
    bruto: int  # lo que pago el alumno por esa clase o video
    comision: int  # parte de LBWUS (IVA incluido)
    abono: int  # lo que le queda al profesor


def _operacion(fecha, alumno, concepto, bruto, tasa):
    return Operacion(fecha, alumno, concepto, bruto, paquetes.comision(bruto, tasa), paquetes.pago_profesor(bruto, tasa))


def detalle(profesor, maximo=MAXIMO):
    """(operaciones, total): las ``maximo`` mas recientes, de la mas nueva a la mas antigua, y cuantas hay en total."""
    operaciones = []
    for inscripcion in (Inscripcion.objects.filter(clase__profesor=profesor).pagables()
                        .select_related('paquete', 'sesion', 'alumno__user')):
        # Cancelada con menos de 4 h: el alumno pierde la clase y el profesor cobra igual (decidido 02-nov).
        tarde = inscripcion.estado == Inscripcion.ESTADO_CANCELADA_TARDE
        usuario = inscripcion.alumno.user
        operaciones.append(_operacion(
            inscripcion.sesion.fecha_hora_inicio, f'{usuario.first_name} {usuario.last_name}'.strip(),
            'Clase cancelada con menos de 4 h' if tarde else 'Clase dictada',
            paquetes.valor_clase(inscripcion), paquetes.COMISION))

    compartidos = VideoCompartido.objects.entregados().filter(paquete__profesor=profesor)
    for valor, fecha, nombre, apellido in videos_con_valor(
            compartidos, 'compartido', 'paquete__alumno__user__first_name', 'paquete__alumno__user__last_name'):
        operaciones.append(_operacion(fecha, f'{nombre} {apellido}'.strip(), 'Video compartido', valor,
                                      paquetes.COMISION_VIDEOS))

    operaciones.sort(key=lambda operacion: operacion.fecha, reverse=True)
    return operaciones[:maximo], len(operaciones)
