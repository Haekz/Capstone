"""La modalidad presencial no existe: todas las clases son online (decidido 07-nov).

Ni en el modelo, ni en el catalogo, ni en los textos publicos. Las clases que estuvieran como presencial
pasaron a online. (El canal "presencial" del apoderado es otra cosa: como se verifica su documento.) Datos ficticios.
"""

import importlib

from django.apps import apps
from django.core.exceptions import ValidationError
from django.urls import reverse

from alumnos.models import Clase
from tests.test_especialidad import CLAVE
from tests.test_filtros_clases import RUT_ALUMNO, EscenarioCatalogo

PAGINAS_PUBLICAS = ['home', 'planes', 'servicios', 'contactos', 'login']


class SinPresencialTests(EscenarioCatalogo):

    def test_la_unica_modalidad_es_online(self):
        self.assertEqual(Clase.MODALIDADES, [('online', 'Online')])
        with self.assertRaises(ValidationError) as error:
            Clase(modalidad='presencial').clean_fields(exclude=['asignatura', 'profesor'])
        self.assertEqual(list(error.exception.message_dict), ['modalidad'])

    def test_las_clases_que_eran_presenciales_pasan_a_online_sin_borrarse(self):
        antes = Clase.objects.count()
        Clase.objects.filter(pk=self.mat_sin_sesiones.pk).update(modalidad='presencial')
        migracion = importlib.import_module('alumnos.migrations.0029_clases_solo_online')
        migracion.presenciales_a_online(apps, None)
        self.assertEqual(Clase.objects.count(), antes)
        self.assertEqual(set(Clase.objects.values_list('modalidad', flat=True)), {'online'})

    def test_el_catalogo_no_tiene_filtro_de_modalidad(self):
        self.client.post(reverse('login'), {'username': RUT_ALUMNO, 'password': CLAVE})
        for params in ({}, {'modalidad': 'presencial'}):  # un enlace viejo con el filtro no rompe ni filtra
            with self.subTest(**params):
                r = self.client.get(reverse('alumno_pag1'), params)
                self.assertEqual(r.status_code, 200)
                self.assertEqual({c.pk for c in r.context['clases_disponibles']}, {c.pk for c in self.habilitadas})
                self.assertNotContains(r, 'name="modalidad"')
                self.assertNotContains(r, 'resencial')

    def test_los_textos_publicos_no_ofrecen_clases_presenciales(self):
        for nombre in PAGINAS_PUBLICAS:
            with self.subTest(pagina=nombre):
                r = self.client.get(reverse(nombre))
                self.assertEqual(r.status_code, 200)
                self.assertNotContains(r, 'resencial')
