"""Proximos horarios libres de cada profesor (tira de dias de la lista de profesores).

alumnos/horarios_profesores.py: una sola consulta para todos los profesores de la lista,
con los mismos criterios de disponibilidad que la ventana de horarios (SesionClase.disponibles).
"""

from datetime import datetime, time, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from alumnos import horarios_profesores
from alumnos.models import Inscripcion, SesionClase
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, Escenario


def sesion_el(clase, dia_local, hora, minuto=0, cupo=5):
    """Sesion de 1 hora un dia local concreto (date) a la hora local dada: para probar los bordes de la ventana."""
    inicio = timezone.make_aware(datetime.combine(dia_local, time(hora, minuto)))
    return SesionClase.objects.create(clase=clase, fecha_hora_inicio=inicio,
                                      fecha_hora_fin=inicio + timedelta(hours=1), cupo_maximo=cupo)


class ProximosHorariosTests(Escenario):

    def horarios(self, *profesores, **extra):
        return horarios_profesores.proximos_horarios(profesores or (self.profe, self.otro), **extra)

    def test_agrupa_por_profesor_y_ordena_por_inicio(self):
        tarde = crear_sesion(self.clase, dias=3)
        pronto = crear_sesion(self.clase, dias=1)
        ajena = crear_sesion(self.clase_otro, dias=2)
        datos = self.horarios()
        self.assertEqual([h['id_sesion'] for h in datos[self.profe.id_profesor]], [pronto.pk, tarde.pk])
        self.assertEqual([h['id_sesion'] for h in datos[self.otro.id_profesor]], [ajena.pk])

    def test_cada_horario_trae_lo_que_necesita_la_tarjeta(self):
        sesion = crear_sesion(self.clase, dias=2)
        local = sesion.inicio_local
        horario = self.horarios()[self.profe.id_profesor][0]
        self.assertEqual(horario, {
            'id_sesion': sesion.pk,
            'asignatura': 'Algebra',
            'fecha': local.strftime('%Y-%m-%d'),
            'hora': local.strftime('%H:%M'),
        })

    def test_profesor_sin_horarios_aparece_con_lista_vacia(self):
        crear_sesion(self.clase, dias=1)
        self.assertEqual(self.horarios()[self.otro.id_profesor], [])

    def test_no_ofrece_canceladas_pasadas_ni_llenas(self):
        buena = crear_sesion(self.clase, dias=1)
        crear_sesion(self.clase, dias=2, estado=SesionClase.ESTADO_CANCELADA)
        crear_sesion(self.clase, dias=-1)
        llena = crear_sesion(self.clase, dias=3, cupo=1)
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=llena,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        self.assertEqual([h['id_sesion'] for h in self.horarios()[self.profe.id_profesor]], [buena.pk])

    def test_ventana_de_7_dias_locales_con_sus_bordes(self):
        hoy = timezone.localdate()
        ultimo = sesion_el(self.clase, hoy + timedelta(days=6), 23, 30)
        sesion_el(self.clase, hoy + timedelta(days=7), 0, 30)  # ya es el octavo dia
        sesion_el(self.clase, hoy + timedelta(days=10), 10)
        self.assertEqual([h['id_sesion'] for h in self.horarios()[self.profe.id_profesor]], [ultimo.pk])

    def test_una_ventana_distinta(self):
        sesion_el(self.clase, timezone.localdate() + timedelta(days=9), 10)
        self.assertEqual(self.horarios(dias=14)[self.profe.id_profesor][0]['fecha'],
                         (timezone.localdate() + timedelta(days=9)).strftime('%Y-%m-%d'))

    def test_oculta_lo_que_el_alumno_ya_reservo(self):
        reservada = crear_sesion(self.clase, dias=1)
        libre = crear_sesion(self.clase, dias=2)
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=reservada,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase, sesion=libre,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        propios = [h['id_sesion'] for h in self.horarios(alumno=self.ana)[self.profe.id_profesor]]
        self.assertEqual(propios, [libre.pk])
        # Cancelada: la plaza vuelve a ser suya.
        Inscripcion.objects.filter(sesion=reservada).update(estado=Inscripcion.ESTADO_CANCELADA)
        propios = [h['id_sesion'] for h in self.horarios(alumno=self.ana)[self.profe.id_profesor]]
        self.assertEqual(propios, [reservada.pk, libre.pk])

    def test_una_sola_consulta_sin_importar_cuantos_profesores_ni_sesiones(self):
        for dias in (1, 2, 3):
            crear_sesion(self.clase, dias=dias)
            crear_sesion(self.clase_otro, dias=dias)
        profesores = (self.profe, self.otro)
        with self.assertNumQueries(1):
            datos = horarios_profesores.proximos_horarios(profesores)
        self.assertEqual({k: len(v) for k, v in datos.items()},
                         {self.profe.id_profesor: 3, self.otro.id_profesor: 3})

    def test_sin_profesores_no_consulta(self):
        with self.assertNumQueries(0):
            self.assertEqual(horarios_profesores.proximos_horarios([]), {})


class VentanaDeHorariosSinPrecioTests(Escenario):
    """El precio es el paquete, no la sesion: la ventana de horarios ya no anuncia un valor (antes decia "Gratis")."""

    def test_el_servicio_ya_no_entrega_precio_por_sesion(self):
        crear_sesion(self.clase, dias=1)
        self.entrar(RUT_ANA)
        sesion = self.client.get(reverse('sesiones_disponibles'), {'clase_id': self.clase.pk}).json()['sesiones'][0]
        self.assertNotIn('precio', sesion)
        self.assertNotIn('precio_formateado', sesion)
        self.assertEqual(sesion['asignatura'], 'Algebra')  # lo demas sigue igual

    def test_la_ventana_no_dibuja_precio(self):
        self.entrar(RUT_ANA)
        html = self.client.get(reverse('alumno_pag1')).content.decode()
        self.assertIn('abrirModalHorarios', html)
        for resto in ('precio_formateado', 'precioUnico', 'safePrecio', 'Gratis'):
            self.assertNotIn(resto, html)


class ListaDeProfesoresTests(Escenario):
    """El portal del alumno entrega a cada tarjeta sus horarios (profesores_js[...]['horarios'])."""

    def tarjetas(self):
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(r.status_code, 200)
        return {t['id']: t for t in r.context['profesores_js']}

    def test_cada_tarjeta_trae_sus_horarios(self):
        mia = crear_sesion(self.clase, dias=1)
        crear_sesion(self.clase_otro, dias=2)
        tarjetas = self.tarjetas()
        self.assertEqual([h['id_sesion'] for h in tarjetas[self.profe.id_profesor]['horarios']], [mia.pk])
        self.assertEqual(len(tarjetas[self.otro.id_profesor]['horarios']), 1)

    def test_profesor_sin_horarios_trae_lista_vacia(self):
        self.assertEqual(self.tarjetas()[self.profe.id_profesor]['horarios'], [])

    def test_no_ofrece_lo_que_el_alumno_ya_reservo(self):
        reservada = crear_sesion(self.clase, dias=1)
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=reservada,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        self.assertEqual(self.tarjetas()[self.profe.id_profesor]['horarios'], [])

    def test_mas_horarios_no_agregan_consultas_al_portal(self):
        self.entrar(RUT_ANA)
        with CaptureQueriesContext(connection) as antes:
            self.client.get(reverse('alumno_pag1'))
        for dias in range(1, 6):
            crear_sesion(self.clase, dias=dias)
            crear_sesion(self.clase_otro, dias=dias)
        with CaptureQueriesContext(connection) as despues:
            self.client.get(reverse('alumno_pag1'))
        self.assertEqual(len(despues), len(antes))

    def test_el_portal_dibuja_la_tira_solo_en_la_lista_de_profesores(self):
        self.entrar(RUT_ANA)
        html = self.client.get(reverse('alumno_pag1')).content.decode()
        self.assertIn('11_horarios_profesor.css', html)  # estilos de la tira
        self.assertIn('function tiraHorarios(t)', html)
        self.assertEqual(html.count('${tiraHorarios(t)}'), 1)  # solo en la lista del panel, no en favoritos
        self.assertIn('mostrarDiaElegido(card);', html)  # en movil, el dia con horas queda a la vista
        # Reservar reutiliza la confirmacion de siempre (la que valida el plan en el servidor).
        self.assertIn('confirmarReservaSesion(hora.dataset.sesion, hora.dataset.asig, hora.dataset.fechahora)', html)
