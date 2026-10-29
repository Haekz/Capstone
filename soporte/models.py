"""Equipo de soporte y tickets.

- Cada verificacion con documentos (identidad o vinculo de un apoderado, titulo de
  un profesor) es un ticket. Se abre cuando queda lista para revisar y se cierra
  cuando alguien decide (o el vinculo se revoca).
- El ticket se asigna solo al agente habilitado en su categoria con menos tickets
  abiertos; el lider de soporte puede reasignarlo.
- Solo el agente asignado ve los documentos y decide. El administrador no.
- Cada asignacion queda registrada: quien tuvo el ticket, desde cuando y quien lo asigno.
- Plazo en dias habiles por categoria (soporte/plazos.py). Reasignar no lo reinicia:
  el plazo es para quien espera la respuesta.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class AgenteSoporte(models.Model):
    """Perfil del rol soporte (ver alumnos/roles.SOPORTE)."""
    id_agente = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='perfil_soporte')
    es_lider = models.BooleanField('líder de soporte', default=False)

    class Meta:
        verbose_name = 'agente de soporte'
        verbose_name_plural = 'agentes de soporte'
        ordering = ['user__first_name']

    def __str__(self):
        return f'{self.nombre} ({self.cargo})'

    @property
    def nombre(self):
        return self.user.first_name

    @property
    def cargo(self):
        return 'Líder de soporte' if self.es_lider else 'Agente de soporte'

    @property
    def categorias(self):
        return set(self.habilitaciones.values_list('categoria', flat=True))


class Ticket(models.Model):
    APODERADOS = 'apoderados'
    TITULOS = 'titulos'
    CATEGORIAS = [(APODERADOS, 'Apoderados y menores'), (TITULOS, 'Títulos de profesores')]
    DIAS_HABILES = {APODERADOS: 5, TITULOS: 5}
    ABIERTO = 'abierto'
    CERRADO = 'cerrado'
    ESTADOS = [(ABIERTO, 'Abierto'), (CERRADO, 'Cerrado')]

    categoria = models.CharField(max_length=12, choices=CATEGORIAS)
    estado = models.CharField(max_length=8, choices=ESTADOS, default=ABIERTO)
    # SET_NULL: si se borra la cuenta del agente, el ticket queda sin asignar.
    asignado = models.ForeignKey(AgenteSoporte, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='tickets')
    # Lo que se revisa: exactamente uno de los tres.
    apoderado = models.ForeignKey('apoderados.Apoderado', on_delete=models.CASCADE, null=True, blank=True,
                                  related_name='tickets')
    vinculo = models.ForeignKey('apoderados.Vinculo', on_delete=models.CASCADE, null=True, blank=True,
                                related_name='tickets')
    profesor = models.ForeignKey('alumnos.Profesor', on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='tickets')
    creado = models.DateTimeField(auto_now_add=True)
    vence = models.DateTimeField()
    cerrado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['creado', 'id']
        constraints = [
            models.CheckConstraint(
                name='ticket_de_un_solo_objeto',
                condition=(Q(apoderado__isnull=False, vinculo__isnull=True, profesor__isnull=True)
                           | Q(apoderado__isnull=True, vinculo__isnull=False, profesor__isnull=True)
                           | Q(apoderado__isnull=True, vinculo__isnull=True, profesor__isnull=False)),
            ),
            # Un solo ticket abierto por cosa revisada.
            models.UniqueConstraint(fields=['apoderado'], condition=Q(estado='abierto'),
                                    name='un_ticket_abierto_por_apoderado'),
            models.UniqueConstraint(fields=['vinculo'], condition=Q(estado='abierto'),
                                    name='un_ticket_abierto_por_vinculo'),
            models.UniqueConstraint(fields=['profesor'], condition=Q(estado='abierto'),
                                    name='un_ticket_abierto_por_profesor'),
        ]

    def __str__(self):
        return f'#{self.pk} {self.asunto} ({self.get_estado_display()})'

    @property
    def asunto(self):
        if self.apoderado_id:
            return f'Identidad de {self.apoderado.nombre}'
        if self.vinculo_id:
            return f'Vínculo {self.vinculo.apoderado.nombre} - {self.vinculo.alumno.user.first_name}'
        return f'Título de {self.profesor.nombre}'

    @property
    def atrasado(self):
        return self.estado == self.ABIERTO and timezone.now() > self.vence


class Habilitacion(models.Model):
    """Categoria en la que un agente recibe tickets."""
    agente = models.ForeignKey(AgenteSoporte, on_delete=models.CASCADE, related_name='habilitaciones')
    categoria = models.CharField(max_length=12, choices=Ticket.CATEGORIAS)

    class Meta:
        verbose_name = 'habilitación'
        verbose_name_plural = 'habilitaciones'
        constraints = [models.UniqueConstraint(fields=['agente', 'categoria'], name='habilitacion_unica')]


class Asignacion(models.Model):
    """Quien tuvo cada ticket y desde cuando. ``autor`` vacio: la asigno el sistema."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='asignaciones')
    agente = models.ForeignKey(AgenteSoporte, on_delete=models.SET_NULL, null=True, related_name='+')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='+')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'asignación'
        verbose_name_plural = 'asignaciones'
        ordering = ['-fecha', '-id']
