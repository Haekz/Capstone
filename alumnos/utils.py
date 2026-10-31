import re
from datetime import date

def validar_rut_chileno(rut):
    rut_clean = rut.replace(".", "").replace("-", "").strip().upper()
    if not re.match(r'^\d{7,8}[0-9K]$', rut_clean): return False
    cuerpo = rut_clean[:-1]
    dv_ingresado = rut_clean[-1]
    suma = 0
    multiplo = 2
    for c in reversed(cuerpo):
        suma += int(c) * multiplo
        multiplo += 1
        if multiplo == 8: multiplo = 2
    resto = suma % 11
    dv_esperado = 11 - resto
    if dv_esperado == 11: dv_calculado = '0'
    elif dv_esperado == 10: dv_calculado = 'K'
    else: dv_calculado = str(dv_esperado)
    return dv_ingresado == dv_calculado

EDAD_ADULTA = 18
EDAD_MINIMA_ESTUDIANTE = 6  # edad minima comercial (decisiones de menores)


def edad(fecha):
    hoy = date.today()
    return hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))


def es_menor(user):
    """True si la cuenta es de un menor. Todos los registros exigen la fecha."""
    return bool(user.fecha_nacimiento) and edad(user.fecha_nacimiento) < EDAD_ADULTA


def error_fecha_nacimiento(fecha, edad_minima=EDAD_ADULTA):
    """Mensaje de error para una fecha de nacimiento, o None si sirve.

    Unica regla de edad para crear alumnos: registro publico, Google y portal
    admin exigen 18. Los menores solo los registra un apoderado verificado
    (app apoderados).
    """
    if fecha >= date.today(): return "La fecha de nacimiento no puede ser actual ni futura."
    if edad(fecha) < edad_minima: return f"Debes ser mayor o igual a {edad_minima} años."
    return None

def usuario_existe(rut, correo, excluir_user=None):
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    usuarios = User.objects.all()
    if excluir_user is not None:
        usuarios = usuarios.exclude(pk=excluir_user.pk)
    # Sin correo (estudiantes menores) solo se revisa el RUT: un correo vacio
    # no puede chocar con las demas cuentas sin correo.
    if correo and usuarios.filter(email__iexact=correo).exists():
        return "El correo electrónico ya está registrado en el sistema."
    if usuarios.filter(Q(username__iexact=rut) | Q(rut__iexact=rut)).exists():
        return "El RUT ingresado ya está registrado en el sistema."
    return None


def formato_clp(valor):
    """Formatea un monto numérico como peso chileno (ej: '$15.000')."""
    try:
        monto = int(round(float(valor or 0)))
    except (TypeError, ValueError):
        monto = 0
    return f"${monto:,}".replace(",", ".")


def validar_imagen_perfil(archivo):
    """Valida extensión, tamaño (<=5MB) y magic bytes/integridad de imagen subida."""
    import os
    from PIL import Image

    if not archivo:
        return "No se recibió ningún archivo."

    max_bytes = 5 * 1024 * 1024
    if getattr(archivo, "size", 0) > max_bytes:
        return "La imagen no puede superar los 5 MB."

    ext = os.path.splitext(getattr(archivo, "name", ""))[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return "Formato no permitido. Usa JPG, PNG o WebP."

    cabecera = archivo.read(16)
    archivo.seek(0)
    es_jpeg = cabecera.startswith(b"\xff\xd8\xff")
    es_png = cabecera.startswith(b"\x89PNG\r\n\x1a\n")
    es_webp = cabecera.startswith(b"RIFF") and cabecera[8:12] == b"WEBP"
    if not (es_jpeg or es_png or es_webp):
        return "El archivo no corresponde a una imagen válida."

    try:
        img = Image.open(archivo)
        img.verify()
        archivo.seek(0)
    except Exception:
        archivo.seek(0)
        return "El archivo de imagen está dañado o no es válido."

    return None
