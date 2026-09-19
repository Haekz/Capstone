from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

def variaciones_rut(texto):
    clean = texto.replace('.', '').replace(' ', '').upper()
    vars_set = {texto.strip(), clean}
    if '-' in clean:
        partes = clean.split('-')
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

        # 1. Buscar en User directamente por username (variantes de RUT), o por email
        users = User.objects.filter(
            Q(username__in=ruts) | Q(email__iexact=identificador)
        )

        # 2. Si no se encuentra en User, buscar en los perfiles por variantes de RUT
        if not users.exists():
            from alumnos.models import Alumno, Profesor, Tutor
            
            alumno = Alumno.objects.filter(rut__in=ruts).select_related('user').first()
            if alumno and alumno.user:
                users = User.objects.filter(pk=alumno.user.pk)
            else:
                profesor = Profesor.objects.filter(rut__in=ruts).select_related('user').first()
                if profesor and profesor.user:
                    users = User.objects.filter(pk=profesor.user.pk)
                else:
                    tutor = Tutor.objects.filter(rut__in=ruts).select_related('user').first()
                    if tutor and tutor.user:
                        users = User.objects.filter(pk=tutor.user.pk)

        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None
