"""Zona horaria: las horas se muestran e ingresan en hora de Chile.

Antes TIME_ZONE='UTC': una sesion de las 10:00 se veia y comparaba corrida.
La migracion 0008 conserva la hora visible de las sesiones ya guardadas.
"""

import importlib
from datetime import datetime, time, timedelta, timezone as dt_timezone
from unittest import mock
from zoneinfo import ZoneInfo

from django.apps import apps
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Asignatura, Clase, Genero, SesionClase
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_progreso_alumno import crear_alumno

migracion = importlib.import_module('alumnos.migrations.0008_sesiones_hora_chile')
UTC, CHILE = dt_timezone.utc, ZoneInfo('America/Santiago')
RUT_ANA = '11111111-1'


class ConversionTests(TestCase):

    def test_sitio_en_hora_de_chile(self):
        self.assertEqual(settings.TIME_ZONE, 'America/Santiago')

    def test_conserva_la_hora_visible_en_verano_e_invierno(self):
        verano = migracion.reinterpretar(datetime(2026, 1, 15, 9, 30, tzinfo=UTC), UTC, CHILE)
        invierno = migracion.reinterpretar(datetime(2026, 7, 15, 9, 30, tzinfo=UTC), UTC, CHILE)
        self.assertEqual(verano.astimezone(UTC).hour, 12)    # Chile UTC-3
        self.assertEqual(invierno.astimezone(UTC).hour, 13)  # Chile UTC-4
        self.assertEqual(timezone.localtime(verano).strftime('%H:%M'), '09:30')

    def test_es_reversible(self):
        original = datetime(2026, 10, 27, 18, 0, tzinfo=UTC)
        ida = migracion.reinterpretar(original, UTC, CHILE)
        self.assertEqual(migracion.reinterpretar(ida, CHILE, UTC), original)


class HorasEnPantallaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ana = crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                     modalidad='online', horario=time(10, 0),
                                     profesor=crear_profesor('20000000-1', 'profe@lbwus.cl', None))
        # "10:00" ingresado en Chile, como desde el admin o cargar_sesiones.
        inicio = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=3), time(10, 0)))
        cls.sesion = SesionClase.objects.create(clase=clase, fecha_hora_inicio=inicio,
                                                fecha_hora_fin=inicio + timedelta(hours=1), cupo_maximo=5)

    def test_modal_de_horarios_en_hora_de_chile(self):
        sesion = self.client.get(reverse('sesiones_disponibles')).json()['sesiones'][0]
        self.assertEqual(sesion['hora_formateada'], '10:00 - 11:00 hrs')

    def test_mensaje_de_reserva_y_admin_en_hora_de_chile(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        r = self.client.post(reverse('reservar_sesion'), data={'id_sesion': self.sesion.pk},
                             content_type='application/json')
        self.assertIn('a las 10:00', r.json()['message'])
        self.assertIn('10:00', str(self.sesion))

    def test_migracion_mueve_las_sesiones_guardadas_en_utc(self):
        # Simula una sesion vieja: "10:00" guardado como 10:00 UTC.
        en_utc = self.sesion.inicio_local.replace(tzinfo=UTC)
        SesionClase.objects.filter(pk=self.sesion.pk).update(
            fecha_hora_inicio=en_utc, fecha_hora_fin=en_utc + timedelta(hours=1))
        migracion.a_hora_chile(apps, None)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.inicio_local.strftime('%H:%M'), '10:00')
        self.assertEqual(self.sesion.fin_local.strftime('%H:%M'), '11:00')


def sesion_antigua(clase, reloj):
    """Sesion de 1 hora como quedaba antes de 0008: la hora de Chile guardada como UTC."""
    inicio = reloj.replace(tzinfo=UTC)
    sesion = SesionClase(clase=clase, fecha_hora_inicio=inicio,
                         fecha_hora_fin=inicio + timedelta(hours=1), cupo_maximo=5)
    sesion.save(skip_clean=True)  # clean() exige fecha futura al crear
    return sesion


class MigracionCambioDeHoraTests(TestCase):
    """Las noches del cambio de hora en Chile: una hora no existe (sept) o se repite (abril)."""

    @classmethod
    def setUpTestData(cls):
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=time(10, 0),
                                         profesor=crear_profesor('20000000-1', 'profe@lbwus.cl', None))

    def migrar(self, reloj):
        sesion = sesion_antigua(self.clase, reloj)
        migracion.a_hora_chile(apps, None)
        sesion.refresh_from_db()
        return sesion

    def test_noche_de_septiembre_no_aborta_la_migracion(self):
        # 00:30 no existe esa noche: antes inicio == fin y fallaba sesion_fin_posterior_a_inicio.
        sesion = self.migrar(datetime(2026, 9, 6, 0, 30))
        self.assertEqual(sesion.fecha_hora_fin - sesion.fecha_hora_inicio, timedelta(hours=1))

    def test_noche_de_abril_conserva_la_duracion(self):
        # 23:30 se repite esa noche: antes la clase de 1 hora quedaba de 2.
        sesion = self.migrar(datetime(2026, 4, 4, 23, 30))
        self.assertEqual(sesion.inicio_local.strftime('%H:%M'), '23:30')
        self.assertEqual(sesion.fecha_hora_fin - sesion.fecha_hora_inicio, timedelta(hours=1))

    def test_ida_y_vuelta_deja_la_base_identica(self):
        relojes = [datetime(2026, 10, 28, 9, 30), datetime(2026, 7, 15, 18, 0), datetime(2026, 4, 4, 23, 30)]
        pks = [sesion_antigua(self.clase, reloj).pk for reloj in relojes]

        def leer():
            return list(SesionClase.objects.filter(pk__in=pks).order_by('pk')
                        .values_list('fecha_hora_inicio', 'fecha_hora_fin'))

        original = leer()
        migracion.a_hora_chile(apps, None)
        self.assertNotEqual(leer(), original)
        migracion.a_utc(apps, None)
        self.assertEqual(leer(), original)


class MesDelPanelProfesorTests(TestCase):

    def test_grafico_mensual_termina_en_el_mes_de_chile(self):
        crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        self.client.post(reverse('login'), {'username': '20000000-1', 'password': CLAVE})
        # 31/01 23:30 en Chile = 01/02 02:30 UTC: el grafico debe terminar en enero.
        with mock.patch('django.utils.timezone.now', return_value=datetime(2026, 2, 1, 2, 30, tzinfo=UTC)):
            r = self.client.get(reverse('panel_profesor'))
        self.assertEqual([m['mes'] for m in r.context['rendimiento_meses']],
                         ['Sep', 'Oct', 'Nov', 'Dic', 'Ene'])
