"""CUENTAS_DEMO_CLAVE=<clave> python manage.py crear_cuentas_demo

Crea cuentas de prueba para recorrer el sistema completo (todas con la misma clave):

  profesor            22222222-2   con titulo aprobado, una clase y 3 sesiones futuras
  alumno regular      11111111-1   sin paquete
  alumno con plan     33333333-3   con un paquete Progreso ya pagado al profesor
  apoderado           44444444-4   identidad verificada
  menor de edad       55555555-5   vinculado a su apoderado (vinculo verificado)

Es idempotente: se puede correr varias veces sin duplicar nada. Por seguridad solo corre con
DEBUG=True (en Railway DEBUG=False) y nunca pisa una cuenta real que ya use uno de esos RUT.
La clave no esta en el codigo: se pasa en la variable CUENTAS_DEMO_CLAVE. Una cuenta de demo que ya existe
conserva la clave con que se creo.
"""

import os
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import (
    Alumno, Asignatura, Clase, Especialidad, Genero, PaqueteClases, Profesor, SesionClase,
)
from apoderados.forms import VERSION_DECLARACION, VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, ClaveDelApoderado, Vinculo

VARIABLE_CLAVE = 'CUENTAS_DEMO_CLAVE'
DOMINIO = 'demo.lbwus.cl'
PLAN_DEL_ALUMNO = 'progreso'
BUY_ORDER = 'DEMO-LBWUS-0001'
DIAS_DE_LAS_SESIONES = (2, 3, 5)

# (clave, rut, nombre, apellido, rol)
CUENTAS = (
    ('profesor', '22222222-2', 'Paula', 'Profesora', 'profesor'),
    ('alumno', '11111111-1', 'Ana', 'Alumna', 'alumno'),
    ('alumno_con_plan', '33333333-3', 'Beto', 'ConPlan', 'alumno'),
    ('apoderado', '44444444-4', 'Marta', 'Apoderada', 'apoderado'),
    ('menor', '55555555-5', 'Nico', 'Menor', 'alumno'),
)


def _hace_anios(anios):
    hoy = date.today()
    try:
        return hoy.replace(year=hoy.year - anios)
    except ValueError:  # 29 de febrero
        return hoy.replace(year=hoy.year - anios, day=28)


class Command(BaseCommand):
    help = 'Crea cuentas de demo: profesor, alumno regular, alumno con plan, apoderado y menor vinculado.'

    def handle(self, *args, **opciones):
        if not settings.DEBUG:
            raise CommandError('Las cuentas de demo tienen una clave conocida: solo se crean con DEBUG=True. No se creó nada.')
        clave = os.environ.get(VARIABLE_CLAVE)
        if not clave:
            raise CommandError(f'Define la variable {VARIABLE_CLAVE} con la clave de las cuentas de demo '
                               '(no se guarda en el código). No se creó nada.')
        with transaction.atomic():
            usuarios = {clave_cuenta: self._usuario(rut, nombre, apellido, rol, clave)
                        for clave_cuenta, rut, nombre, apellido, rol in CUENTAS}
            profesor = self._profesor(usuarios['profesor'])
            self._alumno(usuarios['alumno'], nivel='media', nacimiento=_hace_anios(20))
            con_plan = self._alumno(usuarios['alumno_con_plan'], nivel='media', nacimiento=_hace_anios(21))
            self._paquete(con_plan, profesor)
            apoderado = self._apoderado(usuarios['apoderado'])
            menor = self._alumno(usuarios['menor'], nivel='basica', nacimiento=_hace_anios(12))
            self._vincular(apoderado, menor)
        self._resumen()

    def _usuario(self, rut, nombre, apellido, rol, clave):
        correo = f'{nombre.lower()}.{apellido.lower()}@{DOMINIO}'
        existente = get_user_model().objects.filter(username=rut).first()
        if existente:
            if existente.email != correo:
                raise CommandError(f'El RUT {rut} ya lo usa una cuenta que no es de demo: no se toca. No se creó nada.')
            return existente
        genero, _ = Genero.objects.get_or_create(descripcion='Otro')
        return get_user_model().objects.create_user(
            username=rut, rut=rut, email=correo, password=clave, first_name=nombre, last_name=apellido,
            rol=rol, direccion='Santiago', telefono='911111111', genero=genero,
            fecha_nacimiento=_hace_anios(35),
        )

    def _alumno(self, user, nivel, nacimiento):
        if user.fecha_nacimiento != nacimiento:
            user.fecha_nacimiento = nacimiento
            user.save(update_fields=['fecha_nacimiento'])
        return Alumno.objects.get_or_create(user=user, defaults={'nivel_educacion': nivel})[0]

    def _profesor(self, user):
        especialidad, _ = Especialidad.objects.get_or_create(nombre='Matemáticas')
        profesor, _ = Profesor.objects.get_or_create(
            user=user, defaults={'especialidad': especialidad, 'titulo_estado': Profesor.TITULO_APROBADO})
        clase, _ = Clase.objects.get_or_create(
            asignatura=Asignatura.objects.get_or_create(nombre='Álgebra')[0], profesor=profesor,
            defaults={'modalidad': 'online'})
        if not clase.sesiones.filter(estado=SesionClase.ESTADO_PROGRAMADA, fecha_hora_inicio__gt=timezone.now()).exists():
            for dias in DIAS_DE_LAS_SESIONES:
                inicio = (timezone.now() + timedelta(days=dias)).replace(minute=0, second=0, microsecond=0)
                SesionClase(clase=clase, fecha_hora_inicio=inicio, fecha_hora_fin=inicio + timedelta(hours=1),
                            cupo_maximo=5, estado=SesionClase.ESTADO_PROGRAMADA).save()
        return profesor

    def _paquete(self, alumno, profesor):
        """Paquete ya pagado, como lo deja Webpay al aprobar."""
        if alumno.paquetes.filter(buy_order=BUY_ORDER).exists():
            return
        plan = paquetes.POR_CODIGO[PLAN_DEL_ALUMNO]
        PaqueteClases.objects.create(
            alumno=alumno, profesor=profesor, plan=plan.codigo, clases=plan.clases, tarifa=profesor.tarifa,
            monto=paquetes.precio(plan, profesor.tarifa), dias=plan.vigencia_dias, buy_order=BUY_ORDER,
            estado=PaqueteClases.ESTADO_ACTIVA, fecha_fin=timezone.now() + timedelta(days=plan.vigencia_dias))

    def _apoderado(self, user):
        ahora = timezone.now()
        return Apoderado.objects.get_or_create(user=user, defaults={
            'estado': Apoderado.VERIFICADO, 'correo_verificado': ahora,
            'version_declaracion': VERSION_DECLARACION, 'declaracion_aceptada': ahora})[0]

    def _vincular(self, apoderado, menor):
        Vinculo.objects.get_or_create(apoderado=apoderado, alumno=menor, defaults={
            'parentesco': 'madre', 'estado': Vinculo.VERIFICADO,
            'version_declaracion': VERSION_DECLARACION_VINCULO, 'declaracion_aceptada': timezone.now()})
        ClaveDelApoderado.objects.get_or_create(user=menor.user)  # al cumplir 18 define la suya

    def _resumen(self):
        self.stdout.write(self.style.SUCCESS(f'Cuentas de demo listas (clave de todas: la de {VARIABLE_CLAVE})'))
        for _, rut, nombre, apellido, rol in CUENTAS:
            self.stdout.write(f'  {rol:<10} {rut}  {nombre} {apellido}')
