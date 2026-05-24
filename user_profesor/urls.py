from django.urls import path
from .views import regis_prof, regis_tutor, login_prof, login_admin, panel_profesor, logout_prof, actualizar_perfil_prof

urlpatterns = [
    path('registro_profesor', regis_prof, name='regis_prof'),
    path('registro_tutor', regis_tutor, name='regis_tutor'),
    path('login_profesor', login_prof, name='login_prof'),
    path('login_admin', login_admin, name='login_admin'),
    path('panel', panel_profesor, name='panel_profesor'),
    path('logout_profesor', logout_prof, name='logout_prof'),
    path('actualizar_perfil', actualizar_perfil_prof, name='actualizar_perfil_prof'),
]

