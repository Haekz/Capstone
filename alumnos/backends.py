from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

def variaciones_rut(texto):
    clean = texto.replace('.', '').replace(' ', '').upper()
    vars_set = {texto.strip(), clean}
    
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
