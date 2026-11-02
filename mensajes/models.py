"""Mensajes entre alumno y profesor (paso C1a, decidido 02-nov).

Una conversacion por alumno, profesor y `cliente`: quien habla por el lado del alumno.
Hoy es el propio alumno adulto; en C2 sera cada apoderado, por el menor (que nunca escribe).
El estado de la conversacion (reportada, retencion) y la lectura llegan en C1b-C1d.
"""

from django.conf import settings
from django.db import models
from django.db.models import Exists, F, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce

from alumnos.models import Alumno, Profesor

LARGO_MAX = 1000


class ConversacionQuerySet(models.QuerySet):

    def reportadas(self):
        """Las que alguien reporto (C1c). No es lo mismo que retenidas: una que el lider libero sigue
        estando reportada, pero ya se puede borrar (mensajes/revision.py)."""
        return self.filter(Exists(ReporteConversacion.objects.filter(conversacion=OuterRef('pk'))))

    def visibles(self):
        """Las que sus participantes pueden ver. Si alguien elimino su cuenta, lo que se conservo queda solo
        para soporte, desde el ticket (decidido 02-nov)."""
        return self.filter(cliente__suprimida__isnull=True, alumno__user__suprimida__isnull=True,
                           profesor__user__suprimida__isnull=True)

    def bandeja(self, user, campo_visto):
        """Con `sin_leer` (hay mensajes del otro lado que `user` no ha visto), el texto del ultimo
        mensaje y la fecha de la ultima actividad, de la mas reciente a la mas antigua."""
        ultimos = Mensaje.objects.filter(conversacion=OuterRef('pk')).order_by('-creado', '-pk')
        sin_ver = (Mensaje.objects.filter(conversacion=OuterRef('pk')).exclude(autor=user)
                   .filter(Q(**{f'conversacion__{campo_visto}__isnull': True})
                           | Q(creado__gt=F(f'conversacion__{campo_visto}'))))
        return self.annotate(
            sin_leer=Exists(sin_ver),
            ultimo_texto=Subquery(ultimos.values('texto')[:1]),
            actividad=Coalesce(Subquery(ultimos.values('creado')[:1]), F('creada')),
        ).order_by('-actividad')


class Conversacion(models.Model):
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='conversaciones')
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='conversaciones')
    cliente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    creada = models.DateTimeField(auto_now_add=True)
    # Hasta cuando leyo cada lado: lo posterior de la otra persona queda "sin leer".
    visto_cliente = models.DateTimeField(null=True, blank=True)
    visto_profesor = models.DateTimeField(null=True, blank=True)
    # Cuando se le aviso por ultima vez a cada lado: base de la regla de re-aviso (servicio.REAVISO).
    avisado_cliente = models.DateTimeField(null=True, blank=True)
    avisado_profesor = models.DateTimeField(null=True, blank=True)

    objects = ConversacionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Conversacion'
        verbose_name_plural = 'Conversaciones'
        constraints = [models.UniqueConstraint(fields=['alumno', 'profesor', 'cliente'], name='conversacion_unica')]

    def __str__(self):
        return f'{self.alumno.user.first_name} - {self.profesor.user.first_name}'

    # Como se nombra a cada lado (solo nombre de pila). Del menor habla su apoderado: el profesor ve
    # "Apoderado de <menor>", sin el nombre ni ningun dato del apoderado.
    @property
    def es_de_apoderado(self):
        return self.cliente_id != self.alumno.user_id

    @property
    def nombre_para_profesor(self):
        nombre = self.alumno.user.first_name
        return f'Apoderado de {nombre}' if self.es_de_apoderado else nombre

    @property
    def nombre_para_cliente(self):
        return self.profesor.user.first_name

    def es_participante(self, user):
        return user.pk in (self.cliente_id, self.profesor.user_id)


class Mensaje(models.Model):
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='mensajes')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    texto = models.CharField(max_length=LARGO_MAX)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado', 'pk']
        indexes = [models.Index(fields=['conversacion', 'creado'])]

    def __str__(self):
        return self.texto[:40]


class ReporteConversacion(models.Model):
    """Un participante reporto la conversacion (paso C1c): abre un ticket de soporte, que es la unica
    via para leerla. Mientras exista un reporte, la conversacion no se borra sola, hasta que el lider
    decida liberarla (DecisionRetencion, C1f)."""
    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='reportes')
    ticket = models.OneToOneField('soporte.Ticket', on_delete=models.CASCADE, related_name='reporte_conversacion')
    reportado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Conversacion {self.conversacion_id} reportada (ticket {self.ticket_id})'


class AccesoConversacion(models.Model):
    """Quien de soporte abrio una conversacion reportada, y cuando. Sin agente: su cuenta ya no existe."""
    reporte = models.ForeignKey(ReporteConversacion, on_delete=models.CASCADE, related_name='accesos')
    agente = models.ForeignKey('soporte.AgenteSoporte', on_delete=models.SET_NULL, null=True, related_name='+')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-pk']


class DecisionRetencion(models.Model):
    """Lo que decide el lider de soporte sobre una conversacion reportada cuyo ticket ya se cerro (C1f,
    decidido 02-nov tras la respuesta legal): conservarla como retencion excepcional, o liberarla para que
    vuelva a la regla normal de borrado. Una fila por decision: la vigente es la ultima y las anteriores
    quedan de historial (quien, cuando, por que)."""
    CONSERVAR, LIBERAR = 'conservar', 'liberar'
    DECISIONES = [(CONSERVAR, 'Conservar (retención excepcional)'), (LIBERAR, 'Liberar')]
    RECLAMACION, AUTORIDAD, INVESTIGACION, OTRO = 'reclamacion', 'autoridad', 'investigacion', 'otro'
    MOTIVOS = [(RECLAMACION, 'Reclamación o defensa de derechos'),
               (AUTORIDAD, 'Requerimiento de una autoridad'),
               (INVESTIGACION, 'Investigación en curso'),
               (OTRO, 'Otro (explicar en el fundamento)')]

    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name='decisiones')
    decision = models.CharField(max_length=10, choices=DECISIONES)
    decidida = models.DateTimeField(auto_now_add=True)
    decidida_por = models.ForeignKey('soporte.AgenteSoporte', on_delete=models.SET_NULL, null=True, related_name='+')
    # Solo al conservar: lo que exige registrar la retencion excepcional.
    motivo = models.CharField(max_length=15, choices=MOTIVOS, blank=True)
    alcance = models.TextField('datos y mensajes que se conservan', blank=True)
    fundamento = models.TextField('fundamento', blank=True)
    termino = models.TextField('condición de término', blank=True)
    proxima_revision = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-decidida', '-pk']

    def __str__(self):
        return f'Conversacion {self.conversacion_id}: {self.decision}'
