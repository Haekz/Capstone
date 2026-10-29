"""Modulo de apoderados de estudiantes menores.

- Cuenta del apoderado y verificacion de su identidad.
- Vinculo con cada estudiante menor, verificado uno por uno con el certificado de
  nacimiento (madre o padre) o la resolucion del tribunal (tutor legal). Lo inicia
  el apoderado o un adolescente de 14 a 17 que lo invita por correo.
- El apoderado contrata y reserva por su estudiante (Vinculo.autoriza).
- El vinculo se revoca (apoderado o lider de soporte) o termina solo cuando el
  estudiante cumple 18.
- Documentos: carnet del apoderado y documento del vinculo. Minimizacion de datos: se
  guardan cifrados solo mientras se revisan y se borran al decidir; no se guarda la
  IP. Queda la evidencia de quien reviso y que version de cada declaracion se acepto.
- Cada revision es un ticket de soporte (app soporte): solo el agente asignado la ve.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from alumnos.models import Inscripcion
from alumnos.utils import es_menor
from soporte.models import Ticket
from soporte.tickets import abrir_ticket, cerrar_tickets


class Revision(models.Model):
    """Evidencia de una revision hecha por un agente de soporte. Nunca guarda el documento."""
    APROBAR = 'aprobar'
    RECHAZAR = 'rechazar'
    DECISIONES = [(APROBAR, 'Aprobar'), (RECHAZAR, 'Rechazar')]
    DOCUMENTO_SUBIDO = 'documento'
    # Se revisa el documento subido; presencial y videollamada solo aparecen en
    # revisiones registradas antes de existir los documentos.
    CANALES = [(DOCUMENTO_SUBIDO, 'Documento subido'), ('presencial', 'Presencial'), ('videollamada', 'Videollamada')]

    # SET_NULL: si se borra la cuenta de quien reviso, la evidencia sigue registrada.
    # El nombre del campo se conserva por compatibilidad: guarda al agente de soporte.
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, related_name='+')
    decision = models.CharField(max_length=10, choices=DECISIONES)
    canal = models.CharField(max_length=12, choices=CANALES, blank=True)
    observacion = models.CharField(max_length=300, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['-fecha', '-id']


def _registrar_decision(revisado, revision, administrador):
    """Guarda la evidencia y el nuevo estado juntos: o quedan ambos o ninguno.
    Al decidir (aprobar o rechazar) se borran los documentos y se cierra el ticket."""
    revision.administrador = administrador
    revisado.estado = revisado.VERIFICADO if revision.decision == Revision.APROBAR else revisado.RECHAZADO
    with transaction.atomic():
        revision.save()
        revisado.save(update_fields=['estado'])
        revisado.documentos.all().delete()
        cerrar_tickets(revisado.tickets)


class Apoderado(models.Model):
    CORREO_PENDIENTE = 'correo_pendiente'
    REVISION_PENDIENTE = 'revision_pendiente'
    VERIFICADO = 'verificado'
    RECHAZADO = 'rechazado'
    ESTADOS = [
        (CORREO_PENDIENTE, 'Correo por confirmar'),
        (REVISION_PENDIENTE, 'Identidad en revisión'),
        (VERIFICADO, 'Identidad verificada'),
        (RECHAZADO, 'Verificación rechazada'),
    ]

    id_apoderado = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='perfil_apoderado')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=CORREO_PENDIENTE)
    correo_verificado = models.DateTimeField(null=True, blank=True)
    version_declaracion = models.CharField(max_length=10)
    declaracion_aceptada = models.DateTimeField()
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['creado']

    def __str__(self):
        return f'{self.nombre} ({self.get_estado_display()})'

    @property
    def nombre(self):
        return self.user.first_name

    @property
    def ultima_revision(self):
        return self.revisiones.first()

    @property
    def documentos_completos(self):
        """Subio su carnet por ambos lados: sin eso no se puede aprobar."""
        return set(Documento.CARNET) <= set(self.documentos.values_list('tipo', flat=True))

    def confirmar_correo(self):
        """Marca el correo como propio. El token deja de servir (un solo uso)."""
        if self.estado != self.CORREO_PENDIENTE:
            return
        self.correo_verificado = timezone.now()
        self.estado = self.REVISION_PENDIENTE
        with transaction.atomic():
            self.save(update_fields=['correo_verificado', 'estado'])
            abrir_ticket(Ticket.APODERADOS, apoderado=self)

    def aplicar_revision(self, revision, administrador):
        revision.apoderado = self
        _registrar_decision(self, revision, administrador)
        # Con la identidad verificada, sus vinculos pendientes ya se pueden revisar.
        for vinculo in self.vinculos.filter(estado=Vinculo.PENDIENTE):
            vinculo.abrir_ticket_si_revisable()


class RevisionIdentidad(Revision):
    DOCUMENTOS = [('cedula', 'Cédula de identidad'), ('pasaporte', 'Pasaporte')]

    apoderado = models.ForeignKey(Apoderado, on_delete=models.CASCADE, related_name='revisiones')
    documento = models.CharField('documento revisado', max_length=10, choices=DOCUMENTOS, blank=True)
    rut_coincide = models.BooleanField('el RUT del documento coincide', default=False)

    class Meta(Revision.Meta):
        verbose_name = 'revisión de identidad'
        verbose_name_plural = 'revisiones de identidad'


class Vinculo(models.Model):
    """Apoderado y estudiante menor. Cada vinculo se verifica por separado."""
    PENDIENTE = 'pendiente'
    VERIFICADO = 'verificado'
    RECHAZADO = 'rechazado'
    REVOCADO = 'revocado'
    ESTADOS = [(PENDIENTE, 'Por verificar'), (VERIFICADO, 'Verificado'), (RECHAZADO, 'Rechazado'),
               (REVOCADO, 'Revocado')]
    REVOCABLES = (PENDIENTE, VERIFICADO)
    TUTOR = 'tutor'
    # Madre o padre se acreditan con el certificado de nacimiento; el tutor legal o quien
    # tiene el cuidado personal, con la resolucion del tribunal que lo nombra.
    PARENTESCOS = [('madre', 'Madre'), ('padre', 'Padre'), (TUTOR, 'Tutor legal o cuidado personal')]

    apoderado = models.ForeignKey(Apoderado, on_delete=models.CASCADE, related_name='vinculos')
    alumno = models.ForeignKey('alumnos.Alumno', on_delete=models.CASCADE, related_name='vinculos_apoderado')
    parentesco = models.CharField(max_length=10, choices=PARENTESCOS)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=PENDIENTE)
    version_declaracion = models.CharField(max_length=10)
    declaracion_aceptada = models.DateTimeField()
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'vínculo'
        ordering = ['creado']
        constraints = [models.UniqueConstraint(fields=['apoderado', 'alumno'], name='vinculo_unico')]

    def __str__(self):
        return f'{self.apoderado.nombre} - {self.alumno.user.first_name} ({self.get_estado_display()})'

    @property
    def ultima_revision(self):
        return self.revisiones.first()

    @property
    def apoderado_define_clave(self):
        """Solo si el apoderado creo la cuenta: el adolescente que lo invito maneja la suya."""
        return not SolicitudAdolescente.objects.filter(alumno_id=self.alumno_id).exists()

    @property
    def documento_requerido(self):
        return Documento.RESOLUCION if self.parentesco == self.TUTOR else Documento.CERTIFICADO

    @property
    def documentos_completos(self):
        return self.documentos.filter(tipo=self.documento_requerido).exists()

    def autoriza(self, alumno):
        """Puede actuar por ``alumno``: vinculo verificado de ese estudiante, apoderado
        verificado y estudiante aun menor (a los 18 el vinculo termina solo)."""
        return (self.estado == self.VERIFICADO and self.alumno_id == alumno.pk
                and self.apoderado.estado == Apoderado.VERIFICADO and es_menor(alumno.user))

    @property
    def termino_por_edad(self):
        return self.estado == self.VERIFICADO and not es_menor(self.alumno.user)

    def abrir_ticket_si_revisable(self):
        """El ticket se abre cuando el vinculo ya se puede revisar: con la identidad
        del apoderado verificada. Antes no hay nada que decidir."""
        if self.estado == self.PENDIENTE and self.apoderado.estado == Apoderado.VERIFICADO:
            abrir_ticket(Ticket.APODERADOS, vinculo=self)

    def revocar(self, autor, motivo=''):
        """Revoca y cancela las clases futuras de paquetes pagados con este vinculo
        (la clase vuelve al paquete). Devuelve cuantas reservas se cancelaron."""
        with transaction.atomic():
            Vinculo.objects.select_for_update().filter(pk=self.pk).update(estado=self.REVOCADO)
            self.estado = self.REVOCADO
            Revocacion.objects.create(vinculo=self, autor=autor, motivo=motivo)
            cerrar_tickets(self.tickets)  # si seguia pendiente, ya no hay nada que revisar
            return Inscripcion.objects.filter(
                paquete__compra_apoderado__vinculo=self, estado__in=Inscripcion.ESTADOS_ACTIVOS,
                sesion__fecha_hora_inicio__gt=timezone.now(),
            ).update(estado=Inscripcion.ESTADO_CANCELADA)

    def aplicar_revision(self, revision, administrador):
        revision.vinculo = self
        _registrar_decision(self, revision, administrador)


class RevisionVinculo(Revision):
    vinculo = models.ForeignKey(Vinculo, on_delete=models.CASCADE, related_name='revisiones')
    certificado_coincide = models.BooleanField(
        'el documento confirma el parentesco y los datos', default=False)

    class Meta(Revision.Meta):
        verbose_name = 'revisión de vínculo'
        verbose_name_plural = 'revisiones de vínculos'


class SolicitudAdolescente(models.Model):
    """Un adolescente de 14 a 17 crea su cuenta y pide vincularse con su madre o padre.

    La invitacion al apoderado sale recien cuando el adolescente confirma su
    correo: asi el formulario no sirve para mandar correos a cualquiera.
    """
    alumno = models.OneToOneField('alumnos.Alumno', on_delete=models.CASCADE,
                                  related_name='solicitud_apoderado')
    correo_apoderado = models.EmailField('correo de la madre o el padre')
    correo_confirmado = models.DateTimeField(null=True, blank=True)
    version_declaracion = models.CharField(max_length=10)
    declaracion_aceptada = models.DateTimeField()
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'solicitud de adolescente'
        verbose_name_plural = 'solicitudes de adolescentes'

    @property
    def user(self):
        return self.alumno.user

    @property
    def ultima_invitacion(self):
        return self.invitaciones.first()

    def confirmar_correo(self):
        """True solo la primera vez: la invitacion al apoderado sale una sola vez."""
        if self.correo_confirmado is not None:
            return False
        self.correo_confirmado = timezone.now()
        self.save(update_fields=['correo_confirmado'])
        return True

    def invitar(self, correo):
        """Nueva invitacion; las anteriores dejan de servir (solo vale la ultima)."""
        self.correo_apoderado = correo
        with transaction.atomic():
            self.save(update_fields=['correo_apoderado'])
            return self.invitaciones.create(correo=correo)


class Invitacion(models.Model):
    """El correo solo entrega el enlace: la prueba del vinculo es el certificado."""
    VIGENCIA = timedelta(days=7)
    LIMITE_DIARIO = 5

    solicitud = models.ForeignKey(SolicitudAdolescente, on_delete=models.CASCADE, related_name='invitaciones')
    correo = models.EmailField('correo indicado por el estudiante')
    enviada = models.DateTimeField(auto_now_add=True)
    usada = models.DateTimeField(null=True, blank=True)
    vinculo = models.ForeignKey(Vinculo, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='invitaciones')

    class Meta:
        verbose_name = 'invitación'
        verbose_name_plural = 'invitaciones'
        ordering = ['-enviada', '-id']

    @property
    def vence(self):
        return self.enviada + self.VIGENCIA

    def vigente(self):
        return (self.usada is None and timezone.now() < self.vence
                and self.solicitud.ultima_invitacion == self)

    def aceptar(self, apoderado, parentesco, version_declaracion):
        """Crea el vinculo pendiente: lo verifica soporte con el certificado de nacimiento."""
        with transaction.atomic():
            self.vinculo = Vinculo.objects.create(
                apoderado=apoderado, alumno=self.solicitud.alumno, parentesco=parentesco,
                version_declaracion=version_declaracion, declaracion_aceptada=timezone.now(),
            )
            self.vinculo.abrir_ticket_si_revisable()
            self.usada = timezone.now()
            self.save(update_fields=['vinculo', 'usada'])
        return self.vinculo


class CompraApoderado(models.Model):
    """Paquete de clases que un apoderado pago para su estudiante.

    El paquete (alumnos.PaqueteClases) queda a nombre del estudiante y sigue el
    mismo flujo de Webpay; aqui solo se registra quien lo pago y con que vinculo.
    SET_NULL: si se borra la cuenta o el vinculo, la evidencia del pago queda.
    """
    paquete = models.OneToOneField('alumnos.PaqueteClases', on_delete=models.CASCADE,
                                   related_name='compra_apoderado')
    apoderado = models.ForeignKey(Apoderado, on_delete=models.SET_NULL, null=True, related_name='compras')
    vinculo = models.ForeignKey(Vinculo, on_delete=models.SET_NULL, null=True, related_name='compras')
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'compra de apoderado'
        verbose_name_plural = 'compras de apoderados'
        ordering = ['-creada']


class Revocacion(models.Model):
    """Evidencia de una revocacion: quien, cuando y por que."""
    vinculo = models.OneToOneField(Vinculo, on_delete=models.CASCADE, related_name='revocacion')
    # SET_NULL: si se borra la cuenta del autor, la evidencia sigue registrada.
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    motivo = models.CharField(max_length=300, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'revocación de vínculo'
        verbose_name_plural = 'revocaciones de vínculos'


class ClaveDelApoderado(models.Model):
    """Cuenta cuya contrasena definio el apoderado: al cumplir 18 se exige una nueva."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='clave_del_apoderado')
    definida = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'contraseña definida por el apoderado'
        verbose_name_plural = 'contraseñas definidas por apoderados'


class Documento(models.Model):
    """Copia cifrada de un documento por revisar (ver apoderados/documentos.py).

    Es del apoderado (su carnet) o de un vinculo (certificado o resolucion). Vive solo
    mientras se revisa: se borra al aprobar o rechazar, o a los 30 dias (VIGENCIA).
    """
    CARNET_FRENTE = 'carnet_frente'
    CARNET_REVERSO = 'carnet_reverso'
    CERTIFICADO = 'certificado'
    RESOLUCION = 'resolucion'
    TIPOS = [(CARNET_FRENTE, 'Carnet (frente)'), (CARNET_REVERSO, 'Carnet (reverso)'),
             (CERTIFICADO, 'Certificado de nacimiento'), (RESOLUCION, 'Resolución del tribunal')]
    CARNET = (CARNET_FRENTE, CARNET_REVERSO)
    VIGENCIA = timedelta(days=30)

    apoderado = models.ForeignKey(Apoderado, on_delete=models.CASCADE, null=True, blank=True,
                                  related_name='documentos')
    vinculo = models.ForeignKey(Vinculo, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='documentos')
    tipo = models.CharField(max_length=15, choices=TIPOS)
    formato = models.CharField(max_length=4)  # JPEG o PNG
    contenido = models.BinaryField()  # cifrado: nunca la imagen en claro
    subido = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['subido']
        constraints = [models.CheckConstraint(
            condition=models.Q(apoderado__isnull=False, vinculo__isnull=True)
            | models.Q(apoderado__isnull=True, vinculo__isnull=False),
            name='documento_de_apoderado_o_de_vinculo')]

    @property
    def titular(self):
        """Apoderado que lo subio, sea su carnet o el documento de un vinculo."""
        return self.apoderado or self.vinculo.apoderado


class AccesoDocumento(models.Model):
    """Cada vez que un agente de soporte abre un documento. Queda aunque el documento se borre."""
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, related_name='+')
    apoderado = models.ForeignKey(Apoderado, on_delete=models.CASCADE, related_name='accesos_a_documentos')
    vinculo = models.ForeignKey(Vinculo, on_delete=models.CASCADE, null=True, blank=True, related_name='+')
    tipo = models.CharField(max_length=15, choices=Documento.TIPOS)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'acceso a un documento'
        verbose_name_plural = 'accesos a documentos'
        ordering = ['-fecha', '-id']
