from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


def variaciones_rut(texto):
    if not texto:
        return []
    texto_str = str(texto).strip()
    clean = texto_str.replace('.', '').replace(' ', '').upper()
    vars_set = {texto_str, clean}

    # Si el usuario ingresó el RUT sin guión (ej. 111111111), le inyectamos el guión
    if '-' not in clean and len(clean) in [8, 9]:
        clean = clean[:-1] + '-' + clean[-1]
        vars_set.add(clean)

    if '-' in clean:
        partes = clean.split('-')
        if len(partes) == 2:
            cuerpo, dv = partes[0], partes[1]
            if len(cuerpo) == 8:
                vars_set.add(f"{cuerpo[:2]}.{cuerpo[2:5]}.{cuerpo[5:]}-{dv}")
            elif len(cuerpo) == 7:
                vars_set.add(f"{cuerpo[:1]}.{cuerpo[1:4]}.{cuerpo[4:]}-{dv}")
    return list(vars_set)


def normalizar_rut_canonico(texto):
    """
    Normaliza cualquier formato de RUT a una clave canónica única:
    sin puntos, con guión y DV en mayúsculas (ej: '11111111-1', '12345678-K').
    Si no corresponde a un RUT (ej. es un correo), retorna el texto en minúsculas y limpio.
    """
    if not texto:
        return ''
    t = str(texto).strip()
    if '@' in t:
        return t.lower()

    clean = t.replace('.', '').replace(' ', '').upper()
    if '-' in clean:
        partes = clean.split('-')
        if len(partes) == 2 and partes[0].isdigit():
            return f"{partes[0]}-{partes[1]}"
    elif len(clean) in (8, 9) and clean[:-1].isdigit():
        return f"{clean[:-1]}-{clean[-1]}"

    return clean.lower()


def obtener_identificador_rate_limit(identificador):
    """
    Determina la clave compartida de rate limiting para un intento de inicio de sesión.
    Si el identificador coincide con un usuario existente en la base de datos (por RUT,
    username o correo), retorna el RUT o username canónico para que intentos en diferentes
    formatos compartan el mismo contador persistente.
    """
    if not identificador:
        return ''
    identificador_limpio = str(identificador).strip()
    canon = normalizar_rut_canonico(identificador_limpio)

    try:
        ruts = variaciones_rut(identificador_limpio)
        user = User.objects.filter(
            Q(rut__in=ruts) | Q(username__in=ruts) | Q(email__iexact=identificador_limpio)
        ).only('id', 'rut', 'username').first()

        if user:
            if user.rut:
                return normalizar_rut_canonico(user.rut)
            return user.username.lower()
    except Exception:
        pass

    return canon


class RutOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        identificador = username.strip()
        ruts = variaciones_rut(identificador)

        # 1. Buscar en CustomUser directamente por rut, username o email
        users = User.objects.filter(
            Q(rut__in=ruts) | Q(username__in=ruts) | Q(email__iexact=identificador)
        )

        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None
