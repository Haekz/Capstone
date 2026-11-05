"""Lineas de ayuda que se muestran segun quien es la persona.

Numeros confirmados por el equipo el 03-nov; 147 y 149 ya estaban validados en ChileAtiende (D22). Es el unico lugar
donde se escriben: el portal del menor, la pagina de calificar y el correo al apoderado los toman de aqui.
"""

from collections import namedtuple

from .utils import es_menor

Linea = namedtuple('Linea', 'numero nombre cuando detalle')

EMERGENCIA = Linea('133', 'Emergencias de Carabineros', 'peligro inmediato o agresión en curso.', '')
FONO_FAMILIA = Linea('149', 'Fono Familia', 'violencia intrafamiliar contra una mujer o un hombre.',
                     'Gratuito, las 24 horas.')
FONO_NINOS = Linea('147', 'Fono Niños', 'acoso o vulneración de derechos de una persona menor de edad.',
                   'Gratuito, las 24 horas.')
ORIENTACION_MUJER = Linea(
    '1455', 'Orientación para mujeres', 'violencia de género contra una mujer.',
    'Orientación gratuita, todos los días de 08:00 a 00:00, incluidos festivos. También por WhatsApp al +56 9 9700 7000.')

# Genero.descripcion de alumnos/catalogos.py.
FEMENINO, MASCULINO = 'Femenino', 'Masculino'


def lineas_para(user):
    """Menor: 133, 147 y 149. Mujer adulta: 133, 1455 y 149. Hombre adulto: 133 y 149.

    Quien eligio 'Otro' o 'Prefiero no decir' ve las tres de adultos: es mejor mostrar de mas que dejar a alguien
    sin la linea que necesita."""
    if es_menor(user):
        return (EMERGENCIA, FONO_NINOS, FONO_FAMILIA)
    genero = getattr(user.genero, 'descripcion', None)
    if genero == FEMENINO:
        return (EMERGENCIA, ORIENTACION_MUJER, FONO_FAMILIA)
    if genero == MASCULINO:
        return (EMERGENCIA, FONO_FAMILIA)
    return (EMERGENCIA, FONO_FAMILIA, ORIENTACION_MUJER)
