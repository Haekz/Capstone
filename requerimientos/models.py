"""Registro de requerimientos de autoridad (respuesta legal del 02-nov, E6): cuando un tribunal, la fiscalia u otra
autoridad pide datos de usuarios, queda escrito que se recibio, como se verifico y que se entrego.

Principios: solo los lideres de soporte lo ven; los estados solo avanzan (recibido -> verificado -> cerrado, o
rechazado); solo se entrega con el requerimiento verificado; cada paso deja quien y cuando. El registro NO copia
datos personales ni los documentos: describe categorias de datos y se refiere a las personas por numero de ticket,
nunca por nombre ni RUT.
"""

from django.db import models
from django.utils import timezone


class Requerimiento(models.Model):
    RECIBIDO, VERIFICADO, RECHAZADO, CERRADO = 'recibido', 'verificado', 'rechazado', 'cerrado'
    ESTADOS = [(RECIBIDO, 'Recibido, por verificar'), (VERIFICADO, 'Verificado'),
               (RECHAZADO, 'Rechazado'), (CERRADO, 'Cerrado')]
    ABIERTOS = (RECIBIDO, VERIFICADO)

    autoridad = models.CharField('autoridad que lo pide', max_length=150)
    referencia = models.CharField('oficio, causa o RIT', max_length=100)
    recibido = models.DateField('recibido el')
    vence = models.DateField('plazo que fija la autoridad', null=True, blank=True)
    alcance = models.TextField('qué datos pide', max_length=1000)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=RECIBIDO)
    registrado = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey('soporte.AgenteSoporte', on_delete=models.SET_NULL, null=True, related_name='+')
    # Verificacion (antes de entregar nada).
    verificacion = models.TextField('cómo se verificó', max_length=1000, blank=True)
    verificado = models.DateTimeField(null=True, blank=True)
    verificado_por = models.ForeignKey('soporte.AgenteSoporte', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='+')
    # Cierre: motivo del rechazo o resumen de lo que se hizo.
    resolucion = models.TextField(max_length=1000, blank=True)
    resuelto = models.DateTimeField(null=True, blank=True)
    resuelto_por = models.ForeignKey('soporte.AgenteSoporte', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='+')

    class Meta:
        verbose_name = 'requerimiento de autoridad'
        verbose_name_plural = 'requerimientos de autoridad'
        ordering = ['-registrado', '-pk']

    def __str__(self):
        return f'Requerimiento #{self.pk} ({self.autoridad})'

    @property
    def abierto(self):
        return self.estado in self.ABIERTOS

    @property
    def atrasado(self):
        return self.abierto and self.vence is not None and timezone.localdate() > self.vence


class Entrega(models.Model):
    """Lo que se entrego a la autoridad. Una fila por entrega; no se edita ni se borra."""
    requerimiento = models.ForeignKey(Requerimiento, on_delete=models.CASCADE, related_name='entregas')
    fecha = models.DateTimeField(auto_now_add=True)
    entregada_por = models.ForeignKey('soporte.AgenteSoporte', on_delete=models.SET_NULL, null=True, related_name='+')
    datos = models.TextField('qué se entregó', max_length=1000)
    medio = models.CharField('por qué medio', max_length=100)
    destinatario = models.CharField('a quién', max_length=150)

    class Meta:
        ordering = ['fecha', 'pk']

    def __str__(self):
        return f'Entrega del {self.fecha:%d-%m-%Y} (requerimiento {self.requerimiento_id})'
