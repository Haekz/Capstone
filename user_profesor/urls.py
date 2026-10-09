from django.urls import path
from .views import regis_prof, regis_tutor, panel_profesor, actualizar_perfil_prof, solicitar_retiro

urlpatterns = [
    path('registro_profesor', regis_prof, name='regis_prof'),
    path('registro_tutor', regis_tutor, name='regis_tutor'),
    path('panel', panel_profesor, name='panel_profesor'),
    path('actualizar_perfil', actualizar_perfil_prof, name='actualizar_perfil_prof'),
    path('solicitar_retiro', solicitar_retiro, name='solicitar_retiro'),
    path('subir_titulo', subir_titulo, name='subir_titulo'),
]

