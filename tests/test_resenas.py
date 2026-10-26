"""SCRUM-36: reseñas y calificaciones verificadas.

Cubre las decisiones del equipo: solo califica quien completó una clase, una
reseña por paquete o inscripción, edición solo tras una clase nueva del
paquete, reportes controlados que no ocultan, moderación exclusiva del admin
con registro, protección de datos personales y retiro del contenido ficticio.
"""

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Asignatura, Clase, Genero, Inscripcion, Tutor
from alumnos.roles import ADMIN, ALUMNO, PROFESOR
from resenas.models import ModeracionResena, ReporteResena, Resena
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import dar_paquete
from tests.test_progreso_alumno import crear_alumno

User = get_user_model()
SIN_RESENAS = 'Este profesor aún no tiene reseñas verificadas'


def entrar(client, perfil, rol):
    """Sesión del rol sin pasar por el login (el login tiene su propia matriz)."""
    client.force_login(perfil.user)
    sesion = client.session
    sesion[rol.clave_sesion] = getattr(perfil, rol.campo_id)
    sesion.save()


class BaseResenas(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        cls.otro_profesor = crear_profesor('20000000-2', 'otro@lbwus.cl', None)
        cls.ana = crear_alumno('11111111-1', 'Ana', genero)
        cls.ana.user.last_name = 'Alarcón'
        cls.ana.user.save(update_fields=['last_name'])
        cls.bea = crear_alumno('22222222-2', 'Bea', genero)
        admin_user = User.objects.create_user('33333333-3', password='x', rut='33333333-3', first_name='Tania')
        cls.admin = Tutor.objects.create(user=admin_user)

        cls.clase = cls.crear_clase(cls.profesor, 'Álgebra')
        cls.paquete = dar_paquete(cls.ana, cls.profesor)
        cls.insc_paquete = cls.inscribir(cls.ana, dias=-3, paquete=cls.paquete)
        cls.insc_futura = cls.inscribir(cls.ana, dias=2, paquete=cls.paquete)
        cls.insc_suelta = cls.inscribir(cls.ana, dias=-5)
        cls.insc_bea = cls.inscribir(cls.bea, dias=-4)

    @staticmethod
    def crear_clase(profesor, asignatura):
        return Clase.objects.create(asignatura=Asignatura.objects.create(nombre=asignatura),
                                    modalidad='online', horario=time(10, 0), profesor=profesor)

    @classmethod
    def inscribir(cls, alumno, dias, paquete=None, clase=None):
        sesion = crear_sesion(clase or cls.clase, dias=dias)
        return Inscripcion.objects.create(alumno=alumno, clase=sesion.clase, sesion=sesion, paquete=paquete)

    def resena(self, inscripcion, puntaje=5, comentario='Muy clara', **extra):
        return Resena.objects.create(inscripcion=inscripcion, paquete=inscripcion.paquete,
                                     puntaje=puntaje, comentario=comentario, **extra)

    def calificar(self, inscripcion, puntaje=5, comentario='Muy clara'):
        return self.client.post(reverse('resena_calificar', args=[inscripcion.pk]),
                                {'puntaje': puntaje, 'comentario': comentario})


class CalificarTests(BaseResenas):

    def test_anonimo_va_al_login_y_profesor_vuelve_a_su_panel(self):
        url = reverse('resena_calificar', args=[self.insc_paquete.pk])
        self.assertRedirects(self.client.get(url), reverse('login'), fetch_redirect_response=False)
        entrar(self.client, self.profesor, PROFESOR)
        self.assertRedirects(self.client.post(url, {'puntaje': 1}), reverse('panel_profesor'),
                             fetch_redirect_response=False)
        self.assertFalse(Resena.objects.exists())

    def test_solo_clases_completadas_y_propias(self):
        entrar(self.client, self.ana, ALUMNO)
        for ajena_o_futura in (self.insc_futura, self.insc_bea):
            with self.subTest(inscripcion=ajena_o_futura.pk):
                self.assertEqual(self.calificar(ajena_o_futura).status_code, 404)
        self.assertFalse(Resena.objects.exists())

    def test_publica_una_resena_del_paquete(self):
        entrar(self.client, self.ana, ALUMNO)
        self.calificar(self.insc_paquete, puntaje=4)
        resena = Resena.objects.get()
        self.assertEqual((resena.paquete, resena.inscripcion, resena.puntaje),
                         (self.paquete, self.insc_paquete, 4))

    def test_sin_clase_nueva_no_puede_actualizar(self):
        entrar(self.client, self.ana, ALUMNO)
        self.calificar(self.insc_paquete, puntaje=4)
        respuesta = self.calificar(self.insc_paquete, puntaje=1)
        self.assertEqual(Resena.objects.get().puntaje, 4)
        self.assertContains(self.client.get(respuesta.url), 'Podrás actualizar tu reseña')

    def test_clase_nueva_del_paquete_actualiza_la_misma_resena(self):
        resena = self.resena(self.insc_paquete, puntaje=4)
        Resena.objects.filter(pk=resena.pk).update(actualizada=timezone.now() - timedelta(days=2))
        nueva = self.inscribir(self.ana, dias=-1, paquete=self.paquete)
        entrar(self.client, self.ana, ALUMNO)

        self.calificar(nueva, puntaje=2, comentario='Bajó el nivel')

        self.assertEqual(Resena.objects.count(), 1)
        resena.refresh_from_db()
        self.assertEqual((resena.puntaje, resena.comentario), (2, 'Bajó el nivel'))

    def test_clase_suelta_tiene_su_propia_resena_y_no_se_edita(self):
        entrar(self.client, self.ana, ALUMNO)
        self.calificar(self.insc_suelta, puntaje=3)
        self.calificar(self.insc_suelta, puntaje=5)
        resena = Resena.objects.get()
        self.assertEqual((resena.paquete, resena.puntaje), (None, 3))

    def test_puntaje_fuera_de_rango_y_comentario_largo_se_rechazan(self):
        entrar(self.client, self.ana, ALUMNO)
        for puntaje, comentario in ((6, 'ok'), (0, 'ok'), (5, 'x' * 1001)):
            with self.subTest(puntaje=puntaje, largo=len(comentario)):
                self.assertEqual(self.calificar(self.insc_paquete, puntaje, comentario).status_code, 200)
        self.assertFalse(Resena.objects.exists())

    def test_la_base_de_datos_impide_duplicados(self):
        for inscripcion in (self.insc_paquete, self.insc_suelta):
            self.resena(inscripcion)
            with self.subTest(paquete=inscripcion.paquete_id), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self.resena(inscripcion)


class PerfilTests(BaseResenas):

    def perfil(self):
        entrar(self.client, self.bea, ALUMNO)
        return self.client.get(reverse('perfil_profesor', args=[self.profesor.id_profesor]))

    def test_sin_resenas_muestra_el_mensaje_sin_puntaje(self):
        respuesta = self.perfil()
        self.assertContains(respuesta, SIN_RESENAS)
        self.assertNotContains(respuesta, 'resena-resumen')

    def test_muestra_promedio_cantidad_y_clase_verificada(self):
        self.resena(self.insc_paquete, puntaje=5, comentario='Excelente')
        self.resena(self.insc_bea, puntaje=4, comentario='Buena')
        respuesta = self.perfil()
        for texto in ('4,5', '2 reseñas verificadas', 'Clase verificada', 'Excelente', 'Ana A.'):
            self.assertContains(respuesta, texto)
        self.assertNotContains(respuesta, SIN_RESENAS)

    def test_no_expone_datos_personales_del_autor(self):
        self.resena(self.insc_paquete)
        respuesta = self.perfil()
        for dato in ('Alarcón', '11111111-1', '11111111-1@lbwus.cl'):
            self.assertNotContains(respuesta, dato)

    def test_resena_oculta_no_se_muestra_ni_cuenta(self):
        self.resena(self.insc_paquete, puntaje=5, comentario='Visible')
        self.resena(self.insc_bea, puntaje=1, comentario='Ofensiva', estado=Resena.ESTADO_OCULTA)
        respuesta = self.perfil()
        self.assertContains(respuesta, '1 reseña verificada')
        self.assertNotContains(respuesta, 'Ofensiva')

    def test_no_ofrece_reportar_la_resena_propia(self):
        propia = self.resena(self.insc_bea)
        ajena = self.resena(self.insc_paquete)
        respuesta = self.perfil()
        self.assertNotContains(respuesta, reverse('resena_reportar_alumno', args=[propia.pk]))
        self.assertContains(respuesta, reverse('resena_reportar_alumno', args=[ajena.pk]))


class ReporteTests(BaseResenas):

    def reportar(self, resena, motivo='ofensivo', ruta='resena_reportar_alumno'):
        return self.client.post(reverse(ruta, args=[resena.pk]), {'motivo': motivo, 'detalle': 'Insulta'})

    def test_alumno_reporta_y_la_resena_sigue_visible(self):
        resena = self.resena(self.insc_paquete)
        entrar(self.client, self.bea, ALUMNO)
        self.reportar(resena)
        reporte = ReporteResena.objects.get()
        self.assertEqual((reporte.remitente, reporte.estado), (self.bea.user, ReporteResena.ESTADO_PENDIENTE))
        resena.refresh_from_db()
        self.assertEqual(resena.estado, Resena.ESTADO_VISIBLE)

    def test_reporte_duplicado_propio_o_sin_motivo_se_rechazan(self):
        resena = self.resena(self.insc_paquete)
        entrar(self.client, self.bea, ALUMNO)
        self.reportar(resena)
        self.reportar(resena)
        self.reportar(self.resena(self.insc_bea))  # la suya
        self.reportar(self.resena(self.insc_suelta), motivo='')
        self.assertEqual(ReporteResena.objects.count(), 1)

    def test_limite_diario_de_reportes(self):
        resenas = [self.resena(self.inscribir(self.ana, dias=-10 - i)) for i in range(ReporteResena.LIMITE_DIARIO + 1)]
        entrar(self.client, self.bea, ALUMNO)
        for resena in resenas:
            self.reportar(resena)
        self.assertEqual(ReporteResena.objects.count(), ReporteResena.LIMITE_DIARIO)

    def test_profesor_reporta_su_resena_pero_no_la_de_otro(self):
        suya = self.resena(self.insc_paquete)
        clase_ajena = self.crear_clase(self.otro_profesor, 'Física')
        ajena = self.resena(self.inscribir(self.bea, dias=-2, clase=clase_ajena))
        entrar(self.client, self.profesor, PROFESOR)
        self.assertRedirects(self.reportar(suya, ruta='resena_reportar_profesor'),
                             reverse('resenas_profesor'), fetch_redirect_response=False)
        self.assertEqual(self.reportar(ajena, ruta='resena_reportar_profesor').status_code, 404)
        self.assertEqual(list(ReporteResena.objects.values_list('resena', flat=True)), [suya.pk])

    def test_profesor_ve_sus_resenas_y_no_puede_moderarlas(self):
        resena = self.resena(self.insc_paquete, comentario='Comentario real')
        entrar(self.client, self.profesor, PROFESOR)
        self.assertContains(self.client.get(reverse('resenas_profesor')), 'Comentario real')
        self.client.post(reverse('resena_moderar', args=[resena.pk]), {'accion': 'ocultar', 'criterio': 'normas'})
        resena.refresh_from_db()
        self.assertEqual(resena.estado, Resena.ESTADO_VISIBLE)
        self.assertFalse(ModeracionResena.objects.exists())


class ModeracionTests(BaseResenas):

    def setUp(self):
        self.resena_reportada = self.resena(self.insc_paquete, comentario='Texto reportado')
        ReporteResena.objects.create(resena=self.resena_reportada, remitente=self.bea.user, motivo='ofensivo')

    def moderar(self, accion, criterio=''):
        entrar(self.client, self.admin, ADMIN)
        self.client.post(reverse('resena_moderar', args=[self.resena_reportada.pk]),
                         {'accion': accion, 'criterio': criterio, 'observacion': 'Revisado'})
        self.resena_reportada.refresh_from_db()

    def test_solo_el_admin_entra(self):
        url = reverse('resenas_moderacion')
        for perfil, rol in ((self.ana, ALUMNO), (self.profesor, PROFESOR)):
            with self.subTest(rol=rol.clave):
                entrar(self.client, perfil, rol)
                self.assertRedirects(self.client.get(url), reverse(rol.ruta_portal), fetch_redirect_response=False)
        entrar(self.client, self.admin, ADMIN)
        respuesta = self.client.get(url)
        self.assertContains(respuesta, 'Texto reportado')
        self.assertContains(respuesta, 'Contenido ofensivo')

    def test_ocultar_exige_criterio(self):
        self.moderar('ocultar')
        self.assertEqual(self.resena_reportada.estado, Resena.ESTADO_VISIBLE)
        self.assertFalse(ModeracionResena.objects.exists())

    def test_ocultar_registra_la_decision_y_cierra_los_reportes(self):
        self.moderar('ocultar', criterio='ofensivo')
        self.assertEqual(self.resena_reportada.estado, Resena.ESTADO_OCULTA)
        registro = ModeracionResena.objects.get()
        self.assertEqual((registro.accion, registro.criterio, registro.administrador, registro.observacion),
                         ('ocultar', 'ofensivo', self.admin.user, 'Revisado'))
        self.assertFalse(ReporteResena.objects.filter(estado=ReporteResena.ESTADO_PENDIENTE).exists())

    def test_mantener_cierra_los_reportes_y_sigue_visible(self):
        self.moderar('mantener')
        self.assertEqual(self.resena_reportada.estado, Resena.ESTADO_VISIBLE)
        self.assertEqual(ModeracionResena.objects.get().accion, 'mantener')
        self.assertFalse(ReporteResena.objects.filter(estado=ReporteResena.ESTADO_PENDIENTE).exists())

    def test_restaurar_queda_registrado(self):
        self.moderar('ocultar', criterio='normas')
        self.moderar('restaurar')
        self.assertEqual(self.resena_reportada.estado, Resena.ESTADO_VISIBLE)
        self.assertEqual(list(ModeracionResena.objects.order_by('fecha').values_list('accion', flat=True)),
                         ['ocultar', 'restaurar'])


class ContenidoFicticioTests(BaseResenas):

    def test_nosotros_sin_testimonios_inventados(self):
        respuesta = self.client.get(reverse('nosotros'))
        for texto in ('Maria Oliva', 'Vanessa Stil', 'Experiencias reales'):
            self.assertNotContains(respuesta, texto)

    def test_portal_sin_calificaciones_inventadas_y_con_boton_calificar(self):
        entrar(self.client, self.ana, ALUMNO)
        respuesta = self.client.get(reverse('alumno_pag1'))
        for texto in ('rating:', 'reviews:', 'valoraciones'):
            self.assertNotContains(respuesta, texto)
        self.assertContains(respuesta, reverse('resena_calificar', args=[self.insc_paquete.pk]))
        self.assertNotContains(respuesta, reverse('resena_calificar', args=[self.insc_futura.pk]))

    def test_catalogo_de_cursos_sin_contenido_de_ejemplo(self):
        entrar(self.client, self.ana, ALUMNO)
        respuesta = self.client.get(reverse('alumno_pag1'))
        self.assertContains(respuesta, 'Los cursos grabados estarán disponibles próximamente.')
        for texto in ('Lo más vendido', 'Universidad Python', 'oldPrice', 'gtv-videos-bucket'):
            self.assertNotContains(respuesta, texto)
