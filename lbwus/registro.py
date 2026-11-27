"""Logs sin datos sensibles (SCRUM-100).

Dos capas:
- En cada evento, el codigo enmascara lo que registra (``enmascarar_usuario``, ``enmascarar_token``) y nunca
  pasa contrasenas ni datos de tarjeta.
- ``FormatoSeguro`` (el formateador de la consola en settings.LOGGING) enmascara claves de cadenas de
  conexion, correos, RUT y tokens de Webpay en todo lo que sale, trazas incluidas. Cubre los logs que no
  controlamos: un IntegrityError de PostgreSQL trae el valor repetido ("Key (rut)=(12345678-9)") y un error
  SMTP trae el correo del destinatario. Solo reconoce esos patrones: no reemplaza no registrar secretos.

Este modulo se importa al configurar el logging (antes de cargar las apps): no importa modelos.
"""

import logging
import re

from django.utils.crypto import salted_hmac

# 12.345.678-9, 12345678-9 y 1.234.567-K. Sin guion no se enmascara: seria confundirlo con cualquier numero.
_RUT = re.compile(r'(?<![\w.])(\d{1,2}(?:\.\d{3}){2}|\d{7,8})-([\dkK])(?![\w-])')
_CORREO = re.compile(r'([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)')
# Los tokens de Webpay son 64 caracteres hexadecimales; las ordenes de compra (PQ + 24) no llegan a 40.
_TOKEN = re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{40,}(?![0-9a-fA-F])')
# postgresql://usuario:clave@host, mongodb+srv://usuario:clave@host...: se oculta la clave.
_URI_CON_CLAVE = re.compile(r'([A-Za-z][A-Za-z0-9+.-]*://[^:/@\s]+:)[^@\s]+@')
_NO_SEGURO = re.compile(r'[^A-Za-z0-9@._+-]')


def _rut_visible(cuerpo, dv):
    return f'***{cuerpo.replace(".", "")[-3:]}-{dv.upper()}'


def enmascarar_usuario(texto):
    """Lo que alguien escribio como usuario en el login, sin que se pueda leer entero.

    Correo: primera letra y dominio (``j***@gmail.com``). RUT: ultimos tres digitos y el verificador
    (``***678-K``). Otro texto: dos caracteres (``ad***``).
    """
    # Viene del formulario: solo caracteres seguros, para que nadie invente lineas de log con saltos de linea.
    texto = _NO_SEGURO.sub('', str(texto or ''))[:100]
    if not texto:
        return '-'
    if '@' in texto:
        local, _, dominio = texto.rpartition('@')
        return f'{local[:1]}***@{dominio[:60]}'
    limpio = texto.replace('.', '').replace(' ', '').replace('-', '').upper()
    if 8 <= len(limpio) <= 9 and limpio[:-1].isdigit() and (limpio[-1].isdigit() or limpio[-1] == 'K'):
        return _rut_visible(limpio[:-1], limpio[-1])
    return f'{texto[:2]}***'


def referencia(texto):
    """Huella corta y estable de un identificador: correlaciona intentos sin guardar el dato.

    Depende de SECRET_KEY, asi que no se puede revertir probando RUT con una tabla.
    """
    if not texto:
        return '-'
    return salted_hmac('lbwus.registro.referencia', str(texto)).hexdigest()[:8]


def enmascarar_token(token):
    """Solo los ultimos 6 caracteres: alcanzan para encontrar el pago, no para usar el token."""
    token = str(token or '')
    return f'...{token[-6:]}' if len(token) > 6 else '-'


def limpiar(texto):
    """Enmascara claves de cadenas de conexion, correos, RUT y tokens de Webpay en un texto libre.

    Cubre esos patrones, no cualquier texto: un secreto con otra forma no se reconoce. Por eso cada log
    registra ids y tipos de error, nunca objetos completos ni contrasenas.
    """
    texto = _URI_CON_CLAVE.sub(r'\1***@', texto)
    texto = _CORREO.sub(r'\1***@\2', texto)
    texto = _RUT.sub(lambda m: _rut_visible(m.group(1), m.group(2)), texto)
    return _TOKEN.sub(lambda m: enmascarar_token(m.group(0)), texto)


class FormatoSeguro(logging.Formatter):
    """Formateador de la consola: el mensaje ya formateado (con su traza) pasa por ``limpiar``."""

    def format(self, record):
        return limpiar(super().format(record))
