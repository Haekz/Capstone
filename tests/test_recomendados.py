"""Bloque 'Recomendados' del portal del alumno: los profesores mejor calificados, con un minimo de resenas.

Un solo 5 no basta: hace falta un minimo de resenas visibles (MIN_RESENAS_RECOMENDADO) para entrar. Se ordena por
promedio, luego por mas resenas, y el bloque no aparece si nadie cumple (no se rellena con nadie).
"""

from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.roles import ALUMNO
from resenas.consultas import MIN_RESENAS_RECOMENDADO, TOP_RECOMENDADOS, ids_recomendados
from resenas.models import Resena
from tests.test_resenas import BaseResenas, entrar


def cal(promedio, total):
    return {'promedio': promedio, 'total': total}


class IdsRecomendadosTests(SimpleTestCase):

    def test_el_minimo_de_resenas_deja_fuera_a_quien_tiene_pocas_aunque_sean_perfectas(self):
        calificaciones = {1: cal(5.0, MIN_RESENAS_RECOMENDADO - 1), 2: cal(4.0, MIN_RESENAS_RECOMENDADO)}
        self.assertEqual(ids_recomendados(calificaciones, entre={1, 2}), [2])

    def test_ordena_por_promedio_luego_por_mas_resenas_luego_por_id(self):
        calificaciones = {1: cal(4.5, 4), 2: cal(5.0, 3), 3: cal(4.5, 9), 4: cal(4.5, 4)}
        self.assertEqual(ids_recomendados(calificaciones, entre={1, 2, 3, 4}, tope=4), [2, 3, 1, 4])

    def test_respeta_el_tope(self):
        calificaciones = {i: cal(5.0 - i / 10, 5) for i in range(1, TOP_RECOMENDADOS + 3)}
        resultado = ids_recomendados(calificaciones, entre=set(calificaciones))
        self.assertEqual(len(resultado), TOP_RECOMENDADOS)
        self.assertEqual(resultado, sorted(resultado))  # promedios decrecientes con id creciente

    def test_solo_entre_los_profesores_que_pueden_recomendarse(self):
        calificaciones = {1: cal(5.0, 5), 2: cal(4.0, 5)}
        self.assertEqual(ids_recomendados(calificaciones, entre={2}), [2])

    def test_sin_nadie_que_cumpla_no_hay_recomendados(self):
        self.assertEqual(ids_recomendados({}, entre={1}), [])


class BloqueRecomendadosTests(BaseResenas):

    def portal(self):
        entrar(self.client, self.ana, ALUMNO)
        return self.client.get(reverse('alumno_pag1'))

    def calificar_tres_veces(self, **ultima):
        self.resena(self.insc_paquete, puntaje=5)
        self.resena(self.insc_bea, puntaje=5)
        return self.resena(self.insc_suelta, puntaje=5, **ultima)

    def test_sin_resenas_suficientes_el_bloque_no_aparece(self):
        r = self.portal()
        self.assertEqual(r.context['recomendados'], [])
        self.assertNotContains(r, 'id="recomendados-titulo"')

    def test_con_el_minimo_de_resenas_aparece_con_su_calificacion(self):
        self.calificar_tres_veces()
        r = self.portal()
        self.assertEqual([x['profesor'] for x in r.context['recomendados']], [self.profesor])
        self.assertEqual(r.context['recomendados'][0]['rating'], {'promedio': '5,0', 'total': 3})
        self.assertContains(r, 'id="recomendados-titulo"')
        self.assertContains(r, reverse('perfil_profesor', args=[self.profesor.id_profesor]))

    def test_una_resena_oculta_por_moderacion_no_cuenta_para_el_minimo(self):
        self.calificar_tres_veces(estado=Resena.ESTADO_OCULTA)
        self.assertEqual(self.portal().context['recomendados'], [])
