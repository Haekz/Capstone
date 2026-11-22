"""Portal de soporte (lider), Requerimientos: la estructura de la copia (aviso, paneles, boton, vacios, formulario) con la logica real. Datos ficticios."""
from django.urls import reverse
from django.utils import timezone

from requerimientos.models import Requerimiento as R
from tests.test_requerimientos import Base


class ListaDeRequerimientosTests(Base):

    def pagina(self):
        return self.client.get(reverse('requerimientos')).content.decode()

    def test_sin_requerimientos_se_ven_el_aviso_el_boton_y_los_vacios(self):
        html = self.pagina()
        self.assertIn('<p class="sop-aviso">', html)
        self.assertIn('Antes de entregar cualquier dato hay que verificar el requerimiento.', html)
        self.assertIn('Abiertos <span class="sop-cuenta">0</span>', html)
        self.assertIn(f'<a class="sop-btn sop-btn--primario" href="{reverse("requerimiento_nuevo")}">', html)
        self.assertIn('<p class="sop-vacio">No hay requerimientos abiertos.</p>', html)
        self.assertIn('<p class="sop-vacio">Todavía no hay requerimientos resueltos.</p>', html)
        self.assertNotIn('<table', html)

    def test_un_abierto_sin_plazo_trae_tabla_y_boton_abrir(self):
        requerimiento = self.registrar(vence='')
        html = self.pagina()
        self.assertIn('Abiertos <span class="sop-cuenta">1</span>', html)
        self.assertIn('<div class="sop-tabla">', html)
        self.assertIn('Sin plazo', html)
        self.assertIn(f'<a class="sop-btn sop-btn--primario" href="{reverse("requerimiento_detalle", args=[requerimiento.pk])}"', html)
        self.assertIn(f'aria-label="Abrir el requerimiento {requerimiento.referencia} de {requerimiento.autoridad}"', html)
        self.assertNotIn('No hay requerimientos abiertos.', html)

    def test_un_resuelto_se_ve_con_su_boton_ver(self):
        requerimiento = self.registrar()
        R.objects.filter(pk=requerimiento.pk).update(estado=R.RECHAZADO, resuelto=timezone.now())
        html = self.pagina()
        self.assertIn('<p class="sop-vacio">No hay requerimientos abiertos.</p>', html)
        self.assertIn(f'<a class="sop-btn" href="{reverse("requerimiento_detalle", args=[requerimiento.pk])}"', html)
        self.assertIn('Rechazado', html)
        self.assertNotIn('Todavía no hay requerimientos resueltos.', html)


class RegistrarRequerimientoTests(Base):

    def pagina(self):
        return self.client.get(reverse('requerimiento_nuevo')).content.decode()

    def test_estructura_de_la_copia(self):
        html = self.pagina()
        self.assertIn(f'<a class="sop-volver" href="{reverse("requerimientos")}">', html)
        self.assertIn('<div class="panel sop-panel-angosto">', html)
        self.assertIn('<div class="sop-alerta">', html)
        self.assertIn('<strong>Aquí solo se registra.</strong> No se entrega nada hasta verificarlo.', html)
        self.assertIn('class="apod-form sop-form-dos"', html)
        self.assertIn('Registrar requerimiento</button>', html)

    def test_los_cinco_campos_siguen_siendo_los_mismos(self):
        html = self.pagina()
        for nombre in ('autoridad', 'referencia', 'recibido', 'vence', 'alcance'):
            with self.subTest(campo=nombre):
                self.assertIn(f'name="{nombre}"', html)
        self.assertIn('No copies nombres, RUT ni contenido', html)

    def test_registrar_sigue_funcionando(self):
        self.registrar()
        self.assertEqual(R.objects.count(), 1)
