import re

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

def usuario_existe(rut, correo):
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()
    if User.objects.filter(email__iexact=correo).exists():
        return "El correo electrónico ya está registrado en el sistema."
    if User.objects.filter(Q(username__iexact=rut) | Q(rut__iexact=rut)).exists():
        return "El RUT ingresado ya está registrado en el sistema."
    return None
