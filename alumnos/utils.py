import re
from alumnos.models import Alumno, Profesor, Tutor

def validar_rut_chileno(rut):
    """
    Valida un RUT chileno usando el algoritmo de Módulo 11.
    Acepta formatos con o sin puntos y guión.
    """
    rut_clean = rut.replace(".", "").replace("-", "").strip().upper()

    # Validar formato básico: 7 u 8 dígitos más un dígito verificador (número o 'K')
    if not re.match(r'^\d{7,8}[0-9K]$', rut_clean):
        return False

    cuerpo = rut_clean[:-1]
    dv_ingresado = rut_clean[-1]

    # Calcular dígito verificador usando Módulo 11
    suma = 0
    multiplo = 2
    for c in reversed(cuerpo):
        suma += int(c) * multiplo
        multiplo += 1
        if multiplo == 8:
            multiplo = 2

    resto = suma % 11
    dv_esperado = 11 - resto

    if dv_esperado == 11:
        dv_calculado = '0'
    elif dv_esperado == 10:
        dv_calculado = 'K'
    else:
        dv_calculado = str(dv_esperado)

    return dv_ingresado == dv_calculado


def error_fecha_nacimiento(fecha, edad_minima=18):
    """Mensaje de error para una fecha de nacimiento, o None si sirve."""
    from datetime import date
    hoy = date.today()
    if fecha >= hoy:
        return "La fecha de nacimiento no puede ser actual ni futura."
    edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
    if edad < edad_minima:
        return f"Debes ser mayor o igual a {edad_minima} años."
    return None

def usuario_existe(rut, correo, excluir_user=None):
    """
    Verifica de forma transversal si el RUT o correo ya existe en
    el modelo User o en alguno de los 3 modelos de perfil (Alumno, Profesor, Tutor).
    Retorna un string con el mensaje de error si existe, o None si está libre.

    ``excluir_user``: usuario que no cuenta como duplicado (la cuenta sin
    perfil que dejo un login con Google y que ahora se completa).
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    usuarios = User.objects.all()
    if excluir_user is not None:
        usuarios = usuarios.exclude(pk=excluir_user.pk)
    if usuarios.filter(email__iexact=correo).exists():
        return "El correo electrónico ya está registrado en el sistema."
    if usuarios.filter(Q(username__iexact=rut) | Q(rut__iexact=rut)).exists():
        return "El RUT ingresado ya está registrado en el sistema."

    for modelo in [Alumno, Profesor, Tutor]:
        if modelo.objects.filter(correo_electronico__iexact=correo).exists():
            return "El correo electrónico ya está registrado en el sistema."

        if modelo.objects.filter(rut__iexact=rut).exists():
            return "El RUT ingresado ya está registrado en el sistema."

    return None
