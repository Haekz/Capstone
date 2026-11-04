"""Filtro de datos de contacto en los mensajes (paso C1a, decidido 02-nov: filtro moderado).

Bloquea solo lo que claramente es un contacto: correo, telefono chileno, red social o
app de mensajeria y direccion. Los numeros normales (horas, precios, fechas, ejercicios)
pasan. No es infalible (alguien puede escribir un telefono con palabras): la segunda
defensa es el boton Reportar (C1c). Nunca repite el texto del usuario en el error.
"""

import re
import unicodedata

from django.core.exceptions import ValidationError

CORREO = re.compile(r'[\w.+-]+\s*(?:@|\(\s*at\s*\)|\barroba\b)\s*[\w-]+|\b(?:punto|dot)\s*(?:com|cl|net|org)\b')
# Un telefono chileno tiene 9 digitos (2 a 9 al inicio), o 11 con el 56 del pais.
TELEFONO_CADENA = re.compile(r'\d(?:[\s.\-()]{0,2}\d)*')
TELEFONO = re.compile(r'(?:56)?[2-9]\d{8}')
REDES = re.compile(r'\b(?:whats\s?app|whatsap|wasap|guasap|wsp|wsap|telegram|instagram|insta|facebook|tiktok|'
                   r'snapchat|discord|messenger)\b')
# "calle/avenida/pasaje" + 1 a 3 palabras + numero: asi un "pasaje 3 del texto" no se confunde.
DIRECCION = re.compile(r'\b(?:calle|avenida|avda|av|pasaje|psje|pje)\.?\s+(?:[a-z]+\s+){1,3}#?\d{1,5}\b'
                       r'|\bmi\s+direccion\b|\bvivo\s+en\s+(?:calle|avenida|pasaje)\b')


class ContactoBloqueado(ValidationError):
    pass


def _normalizar(texto):
    """Minusculas y sin tildes: 'Dirección' y 'direccion' se detectan igual."""
    sin_tildes = ''.join(c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c))
    return sin_tildes.lower()


def _hay_telefono(texto):
    return any(TELEFONO.fullmatch(re.sub(r'\D', '', cadena)) for cadena in TELEFONO_CADENA.findall(texto))


def motivo(texto):
    """Que dato de contacto trae el texto (para decirselo al usuario), o None si esta limpio."""
    texto = _normalizar(texto)
    if CORREO.search(texto):
        return 'un correo electrónico'
    if _hay_telefono(texto):
        return 'un teléfono'
    if REDES.search(texto):
        return 'una red social o app de mensajería'
    if DIRECCION.search(texto):
        return 'una dirección'
    return None


def exigir_sin_contacto(texto):
    encontrado = motivo(texto)
    if encontrado:
        raise ContactoBloqueado(f'No puedes compartir {encontrado} por aquí. Coordinen las clases dentro de LBWUS.')
