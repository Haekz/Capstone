"""Correo con diseno sobre una clase (reserva, cancelacion, reagenda...): una sola forma de armarlo para todos.

Lo usan los avisos al profesor (avisos_profesor.py) y al alumno o su apoderado (agenda/avisos_alumno.py). Lleva el
texto de respaldo y la version con diseno. Privacidad: solo lo que se le pasa en `lineas`; nada de RUT, correo ni
telefono de nadie (decidido 21-nov: solo nombre y apellido).
"""

from django.conf import settings

from .correo import enviar


def enviar_aviso_clase(usuario, asunto, titulo, lineas, boton_texto, ruta):
    """Devuelve False si el correo no salio (ver correo.enviar). `ruta` es interna: aqui se vuelve enlace completo."""
    contexto = {
        'nombre': usuario.first_name,
        'titulo': titulo,
        'lineas': lineas,
        'boton_texto': boton_texto,
        'enlace': f'{settings.SITIO_URL}{ruta}',
    }
    return enviar(asunto, 'correos/aviso_clase.txt', contexto, usuario.email, plantilla_html='correos/aviso_clase.html')
