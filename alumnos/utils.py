import re

from django.utils import timezone

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
    hoy = timezone.localdate()
    return hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))


def entero(valor):
    """El numero que mando el navegador, o None si no lo es (lo que llega por POST nunca se da por bueno)."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def es_menor(user):
    """True si la cuenta es de un menor. Todos los registros exigen la fecha."""
    return bool(user.fecha_nacimiento) and edad(user.fecha_nacimiento) < EDAD_ADULTA


def nombre_para_el_profesor(user):
    """Lo que el profesor puede ver del alumno (decidido 21-nov): nombre y apellido de un adulto; de un menor, solo el
    nombre de pila."""
    return user.first_name if es_menor(user) else user.get_full_name()


def error_fecha_nacimiento(fecha, edad_minima=EDAD_ADULTA):
    """Mensaje de error para una fecha de nacimiento, o None si sirve.

    Unica regla de edad para crear alumnos: registro publico, Google y portal
    admin exigen 18. Los menores solo los registra un apoderado verificado
    (app apoderados).
    """
    if fecha >= timezone.localdate(): return "La fecha de nacimiento no puede ser actual ni futura."
    if edad(fecha) < edad_minima: return f"Debes ser mayor o igual a {edad_minima} años."
    return None

CORREO_YA_REGISTRADO = "El correo electrónico ya está registrado en el sistema."
RUT_YA_REGISTRADO = "El RUT ingresado ya está registrado en el sistema."


def _otras_cuentas(excluir_user):
    from django.contrib.auth import get_user_model
    usuarios = get_user_model().objects.all()
    return usuarios if excluir_user is None else usuarios.exclude(pk=excluir_user.pk)


def correo_en_uso(correo, excluir_user=None):
    """True si otra cuenta ya usa el correo, sin distinguir mayusculas (como el login)."""
    return bool(correo) and _otras_cuentas(excluir_user).filter(email__iexact=correo).exists()


def rut_en_uso(rut, excluir_user=None):
    """True si otra cuenta ya tiene este RUT escrito en cualquier formato: con o sin puntos y guion, k o K.

    Los RUT se guardan como se escribieron y el login acepta todos los formatos: comparar el texto tal cual dejaba
    crear una segunda cuenta de la misma persona con '12.345.678-5' si existia '12345678-5' (20-nov).
    """
    from django.db.models import Q
    from .backends import normalizar_rut_canonico, variaciones_rut
    if not rut:
        return False
    canon = normalizar_rut_canonico(rut)
    variantes = set(variaciones_rut(canon)) | {canon.replace('-', ''), str(rut).strip()}
    variantes |= {v.lower() for v in variantes}
    return _otras_cuentas(excluir_user).filter(Q(rut__in=variantes) | Q(username__in=variantes)).exists()


def usuario_existe(rut, correo, excluir_user=None):
    # Sin correo (estudiantes menores) solo se revisa el RUT: un correo vacio
    # no puede chocar con las demas cuentas sin correo.
    if correo_en_uso(correo, excluir_user):
        return CORREO_YA_REGISTRADO
    if rut_en_uso(rut, excluir_user):
        return RUT_YA_REGISTRADO
    return None


# Chile: todo numero tiene 9 digitos desde 2016 (celulares 9..., fijos con su codigo de area); el +56 es opcional.
TELEFONO_CHILENO = re.compile(r'(?:\+?56)?([2-9]\d{8})')


def normalizar_telefono(texto):
    """Telefono chileno a sus 9 digitos, sin prefijo ni separadores ('+56 9 1234 5678' -> '912345678').

    Vacio -> ''. None si no es un numero chileno.
    """
    limpio = re.sub(r'[\s().-]', '', texto or '')
    if not limpio:
        return ''
    numero = TELEFONO_CHILENO.fullmatch(limpio)
    return numero.group(1) if numero else None


def validar_clave_nueva(password, rut, correo, nombre=''):
    """validate_password contra el RUT, el correo y (si se da) el nombre de la cuenta que se crea.

    Sin usuario, Django no tiene con que compararla: la clave igual al RUT o al
    correo pasaba (Seg-3). Lanza ValidationError, como validate_password.
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    validate_password(password, get_user_model()(username=rut or '', email=correo or '', first_name=nombre or ''))
def formato_clp(valor):
    """Formatea un monto numérico como peso chileno (ej: '$15.000')."""
    try:
        monto = int(round(float(valor or 0)))
    except (TypeError, ValueError):
        monto = 0
    return f"${monto:,}".replace(",", ".")
