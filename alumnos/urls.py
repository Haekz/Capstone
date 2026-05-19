#from django.conf.urls import url
from django.urls import path
from .views import home, contactos, nosotros, planes, servicios, simulador, opcion_user, regis_alum, alumnos_reg

urlpatterns = [
    path('', home, name='home'),
    path('contactos', contactos, name='contactos'),
    path('nosotros', nosotros, name='nosotros'),
    path('planes', planes, name='planes'),
    path('servicios', servicios, name='servicios'),
    path('simulador', simulador, name='simulador'),
    path('select', opcion_user, name='opcion_user'),
    path('registro_alumno', regis_alum, name='regis_alum'),
    path('alumnos_reg', alumnos_reg, name='alumnos_reg'),
]
