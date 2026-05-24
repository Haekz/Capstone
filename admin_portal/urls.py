from django.urls import path
from .views import (
    menu, reporte_alumnos, home_adm, planes_adm, nosotros_adm, contactos_adm,
    crud, alumnos_Add, alumnos_del, alumnos_findEdit, alumnos_Update,
    dashboard_admin, resolver_reporte
)

urlpatterns = [
    # esta parte es de las rutas del portal del administrador
    path('menu', menu, name='menu'),
    path('dashboard/', dashboard_admin, name='dashboard_admin'),
    path('reporte_alumnos', reporte_alumnos, name='reporte_alumnos'),
    path('home_adm', home_adm, name='home_adm'),
    path('planes_adm', planes_adm, name='planes_adm'),
    path('nosotros_adm', nosotros_adm, name='nosotros_adm'),
    path('contactos_adm', contactos_adm, name='contactos_adm'),
    path('resolver_reporte/<int:pk>/', resolver_reporte, name='resolver_reporte'),

    # esta parte es de las rutas CRUD de alumnos
    path('crud/', crud, name='crud'),
    path('alumnos_Add', alumnos_Add, name='alumnos_Add'),
    path('alumnos_del/<str:pk>/', alumnos_del, name='alumnos_del'),
    path('alumnos_findEdit/<str:pk>/', alumnos_findEdit, name='alumnos_findEdit'),
    path('alumnos_Update', alumnos_Update, name='alumnos_Update'),
]