"""Retiros de los profesores: banco, cuenta bancaria cifrada y solicitudes de retiro."""

from datetime import timedelta
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from .. import catalogos
from ..cifrado import cifrador
from .usuarios import Profesor


class Banco(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    
    def __str__(self):
        return self.nombre


TIPOS_CUENTA = [('rut_vista', 'Cuenta Rut / Vista'), ('corriente', 'Cuenta Corriente'), ('ahorro', 'Cuenta de Ahorro')]


class CuentaBancaria(models.Model):
    """Cuenta donde se le paga al profesor: una sola y a su nombre.

    El titular es siempre el RUT del profesor; al transferir con ese RUT, el banco
    rechaza una cuenta ajena. El numero va cifrado y se muestra enmascarado.
    Tras un cambio confirmado no se le paga durante ESPERA_CAMBIO (P3).
    """
    ESPERA_CAMBIO = timedelta(hours=48)

    profesor = models.OneToOneField(Profesor, on_delete=models.CASCADE, related_name='cuenta_bancaria')
    banco = models.CharField(max_length=40, choices=[(b, b) for b in catalogos.BANCOS])
    tipo_cuenta = models.CharField(max_length=10, choices=TIPOS_CUENTA)
    numero_cifrado = models.BinaryField()
    ultimos_digitos = models.CharField(max_length=4)
    actualizada = models.DateTimeField(auto_now=True)
    cambiada_en = models.DateTimeField(null=True, blank=True)  # None: es la primera cuenta

    @property
    def pagable_desde(self):
        return self.cambiada_en + self.ESPERA_CAMBIO if self.cambiada_en else None

    @property
    def bloqueada(self):
        return self.cambiada_en is not None and timezone.now() < self.pagable_desde

    @staticmethod
    def _cifrador():
        return cifrador('cuentas-bancarias')

    def asignar_numero(self, valor):
        numero = (valor or '').replace(' ', '').replace('-', '')
        if not numero.isdigit() or not 5 <= len(numero) <= 20:
            raise ValidationError('El número de cuenta debe tener entre 5 y 20 dígitos.')
        self.numero_cifrado = self._cifrador().encrypt(numero.encode())
        self.ultimos_digitos = numero[-4:]

    @property
    def numero(self):
        return self._cifrador().decrypt(bytes(self.numero_cifrado)).decode()  # PostgreSQL entrega un memoryview

    @property
    def enmascarado(self):
        return f'•••• {self.ultimos_digitos}'


class SolicitudRetiro(models.Model):
    """Retiro de saldo de un profesor. Los estados solo avanzan:
    pendiente -> aprobado -> pagado, o pendiente -> rechazado.

    Aprobar no es pagar: la plata se mueve en el banco y despues se registra
    aqui el numero de operacion. Cada paso guarda quien lo hizo.
    """
    PENDIENTE, APROBADO, PAGADO, RECHAZADO = 'pendiente', 'aprobado', 'pagado', 'rechazado'

    id_solicitud = models.AutoField(primary_key=True)
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='retiros')
    monto = models.IntegerField()
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=[(PENDIENTE, 'Pendiente'), (APROBADO, 'Aprobado'), (PAGADO, 'Pagado'), (RECHAZADO, 'Rechazado')], default=PENDIENTE)
    banco = models.ForeignKey(Banco, on_delete=models.SET_NULL, null=True)
    tipo_cuenta = models.CharField(max_length=40, choices=TIPOS_CUENTA, default='rut_vista')
    numero_cuenta = models.CharField(max_length=40, blank=True, default='')
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    # SET_NULL: si se borra la cuenta del admin, el retiro se conserva.
    resuelto_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')
    motivo_rechazo = models.TextField(blank=True, default='')
    pagado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    numero_operacion = models.CharField(max_length=40, blank=True, default='')
    fecha_pago = models.DateTimeField(null=True, blank=True)
    pagar_el = models.DateField(null=True, blank=True)  # lunes siguiente al corte (alumnos/liquidacion.py)

    def __str__(self):
        return f"Retiro #{self.id_solicitud} - {self.profesor.user.first_name} (${self.monto})"

    def _exigir(self, estado):
        if self.estado != estado:
            raise ValidationError(f'No se puede: el retiro #{self.id_solicitud} está {self.get_estado_display().lower()}.')

    def aprobar(self, usuario):
        self._exigir(self.PENDIENTE)
        self.estado, self.resuelto_por, self.fecha_resolucion = self.APROBADO, usuario, timezone.now()
        self.save()

    def rechazar(self, usuario, motivo):
        self._exigir(self.PENDIENTE)
        motivo = motivo.strip()
        if not motivo:
            raise ValidationError('Escribe el motivo del rechazo: el profesor lo verá.')
        self.estado, self.resuelto_por, self.fecha_resolucion = self.RECHAZADO, usuario, timezone.now()
        self.motivo_rechazo = motivo
        self.save()

    def marcar_pagado(self, usuario, numero_operacion):
        self._exigir(self.APROBADO)
        cuenta = CuentaBancaria.objects.filter(profesor_id=self.profesor_id).first()
        if cuenta is not None and cuenta.bloqueada:
            desde = timezone.localtime(cuenta.pagable_desde).strftime('%d/%m/%Y %H:%M')
            raise ValidationError(f'La cuenta del profesor cambió hace menos de 48 h: se puede pagar desde el {desde}.')
        numero = numero_operacion.strip()
        if not numero:
            raise ValidationError('Escribe el número de operación de la transferencia.')
        self.estado, self.pagado_por, self.fecha_pago = self.PAGADO, usuario, timezone.now()
        self.numero_operacion = numero[:40]
        self.save()
