"""Comando tareas_diarias: el unico cron de Railway, corre todas las tareas diarias."""
from io import StringIO
from unittest import mock

from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.test import TestCase

from alumnos.management.commands.tareas_diarias import TAREAS

LLAMAR = 'alumnos.management.commands.tareas_diarias.call_command'


def _nombres(llamar):
    return [llamada.args[0] for llamada in llamar.call_args_list]


class TareasDiariasTests(TestCase):

    def test_corre_cada_tarea_una_vez_y_en_orden(self):
        with mock.patch(LLAMAR) as llamar:
            call_command('tareas_diarias', stdout=StringIO())
        self.assertEqual(_nombres(llamar), list(TAREAS))

    def test_la_agenda_va_primero(self):
        self.assertEqual(TAREAS[0], 'generar_bloques')

    def test_si_una_falla_corren_las_demas_y_termina_con_error_que_la_nombra(self):
        def llamar_fallando(nombre, **kwargs):
            if nombre == 'borrar_documentos_vencidos':
                raise RuntimeError('base caida')

        with mock.patch(LLAMAR, side_effect=llamar_fallando) as llamar, \
                self.assertLogs('alumnos.management.commands.tareas_diarias', 'ERROR'), \
                self.assertRaisesMessage(CommandError, f'Fallaron 1 de {len(TAREAS)}: borrar_documentos_vencidos'):
            call_command('tareas_diarias', stdout=StringIO())
        self.assertEqual(_nombres(llamar), list(TAREAS))

    def test_cada_tarea_es_un_comando_que_existe(self):
        self.assertEqual(set(TAREAS) - set(get_commands()), set())

    def test_sin_datos_corren_todas_de_verdad(self):
        salida = StringIO()
        call_command('tareas_diarias', stdout=salida)
        self.assertIn(f'Tareas diarias completas: {len(TAREAS)}', salida.getvalue())
        for tarea in TAREAS:
            self.assertIn(f'== {tarea}', salida.getvalue())
