"""Modulo de apoderados (decisiones de menores).

Fase 1a: cuenta del apoderado y verificacion de su identidad.
Fase 1b: vinculo con cada estudiante menor, verificado uno por uno con el
certificado de nacimiento (solo madre o padre en el MVP). El vinculo lo inicia
el apoderado (1b-i) o un adolescente de 14 a 17 que lo invita por correo (1b-ii).

Una cuenta o un vinculo verificados NO habilitan reservas, compras ni clases:
eso llega con la contratacion por el apoderado (fase 1c). Minimizacion de
datos: no se guardan copias de documentos ni la IP; solo la evidencia de que un
administrador reviso, y que version de cada declaracion se acepto.
"""

from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class Revision(models.Model):
    """Evidencia de una revision hecha por un administrador. Nunca guarda el documento."""
    APROBAR = 'aprobar'
    RECHAZAR = 'rechazar'
    DECISIONES = [(APROBAR, 'Aprobar'), (RECHAZAR, 'Rechazar')]
    CANALES = [('presencial', 'Presencial'), ('videollamada', 'Videollamada')]

    # SET_NULL: si se borra la cuenta del admin, la evidencia sigue registrada.
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
    """Guarda la evidencia y el nuevo estado juntos: o quedan ambos o ninguno."""
    revision.administrador = administrador
    revisado.estado = revisado.VERIFICADO if revision.decision == Revision.APROBAR else revisado.RECHAZADO
    with transaction.atomic():
        revision.save()
        revisado.save(update_fields=['estado'])


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

    def confirmar_correo(self):
        """Marca el correo como propio. El token deja de servir (un solo uso)."""
        if self.estado != self.CORREO_PENDIENTE:
            return
        self.correo_verificado = timezone.now()
        self.estado = self.REVISION_PENDIENTE
        self.save(update_fields=['correo_verificado', 'estado'])

    def aplicar_revision(self, revision, administrador):
        revision.apoderado = self
        _registrar_decision(self, revision, administrador)


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
    ESTADOS = [(PENDIENTE, 'Por verificar'), (VERIFICADO, 'Verificado'), (RECHAZADO, 'Rechazado')]
    # MVP: solo se acepta el certificado de nacimiento, que acredita madre o padre.
    PARENTESCOS = [('madre', 'Madre'), ('padre', 'Padre')]

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
        """Solo si el apoderado creo la cuenta (1b-i): el adolescente maneja la suya (1b-ii)."""
        return not SolicitudAdolescente.objects.filter(alumno_id=self.alumno_id).exists()

    def aplicar_revision(self, revision, administrador):
        revision.vinculo = self
        _registrar_decision(self, revision, administrador)


class RevisionVinculo(Revision):
    vinculo = models.ForeignKey(Vinculo, on_delete=models.CASCADE, related_name='revisiones')
    certificado_coincide = models.BooleanField(
        'el certificado de nacimiento confirma el parentesco y los datos', default=False)

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
        """Crea el vinculo pendiente: lo verifica un admin con el certificado de nacimiento."""
        with transaction.atomic():
            self.vinculo = Vinculo.objects.create(
                apoderado=apoderado, alumno=self.solicitud.alumno, parentesco=parentesco,
                version_declaracion=version_declaracion, declaracion_aceptada=timezone.now(),
            )
            self.usada = timezone.now()
            self.save(update_fields=['vinculo', 'usada'])
        return self.vinculo
