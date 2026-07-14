from django.urls import path
from .views import (
    home, contactos, nosotros, planes, servicios, simulador, opcion_user, 
    regis_alum, alumnos_reg, alumno_pag1, crud, alumnos_Add, alumnos_del, 
    alumnos_findEdit, alumnos_Update, pago, confirmacion, iniciar_webpay
)

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
    path('alumno_home', alumno_pag1, name='alumno_pag1'),

    # esta parte es de las rutas CRUD de alumnos
    path('crud/', crud, name='crud'),
    path('alumnos_Add', alumnos_Add, name='alumnos_Add'),
    path('alumnos_del/<str:pk>/', alumnos_del, name='alumnos_del'),
    path('alumnos_findEdit/<str:pk>/', alumnos_findEdit, name='alumnos_findEdit'),
    path('alumnos_Update', alumnos_Update, name='alumnos_Update'),
    path('pago', pago, name='pago'),
    path('confirmacion', confirmacion, name='confirmacion'),
    path('iniciar-webpay/', iniciar_webpay, name='iniciar_webpay'),
]
