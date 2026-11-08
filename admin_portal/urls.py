from django.urls import path
from .views import (
    menu, reporte_alumnos, home_adm, planes_adm, nosotros_adm,
    crud, alumnos_Add, alumnos_del, alumnos_findEdit, alumnos_Update,
    dashboard_admin, logout_admin,
    aprobar_retiro, rechazar_retiro, marcar_pagado_retiro
)
from .asignaturas import asignaturas_adm, crear_asignatura, eliminar_asignatura, renombrar_asignatura
from .escalados import casos_escalados, crear_asignatura_pedida, indicar_escalado
from .titulos import (titulos_adm, ver_titulo, resolver_titulo, ver_especializacion, resolver_especializacion,
                      pedir_asignatura)

urlpatterns = [
    # esta parte es de las rutas del portal del administrador
    path('menu', menu, name='menu'),
    path('dashboard/', dashboard_admin, name='dashboard_admin'),
    path('reporte_alumnos', reporte_alumnos, name='reporte_alumnos'),
    path('home_adm', home_adm, name='home_adm'),
    path('planes_adm', planes_adm, name='planes_adm'),
    path('nosotros_adm', nosotros_adm, name='nosotros_adm'),
    # Las clases ya no se crean ni eliminan aqui: las crea soporte al aprobar (fase 3).
    path('aprobar_retiro/<int:pk>/', aprobar_retiro, name='aprobar_retiro'),
    path('rechazar_retiro/<int:pk>/', rechazar_retiro, name='rechazar_retiro'),
    path('pagar_retiro/<int:pk>/', marcar_pagado_retiro, name='marcar_pagado_retiro'),

    # Casos graves que escala el lider de soporte (D5, revisada 05-nov)
    path('casos-escalados/', casos_escalados, name='casos_escalados'),
    path('asignaturas/', asignaturas_adm, name='asignaturas_adm'),
    path('asignaturas/crear/', crear_asignatura, name='crear_asignatura'),
    path('asignaturas/<int:pk>/renombrar/', renombrar_asignatura, name='renombrar_asignatura'),
    path('asignaturas/<int:pk>/eliminar/', eliminar_asignatura, name='eliminar_asignatura'),
    path('casos-escalados/<int:pk>/indicar/', indicar_escalado, name='indicar_escalado'),
    path('casos-escalados/<int:pk>/crear-asignatura/', crear_asignatura_pedida, name='crear_asignatura_pedida'),

    # Titulos profesionales de profesores
    path('titulos/', titulos_adm, name='titulos_adm'),
    path('titulos/<int:pk>/archivo/', ver_titulo, name='ver_titulo'),
    path('titulos/<int:pk>/resolver/', resolver_titulo, name='resolver_titulo'),
    path('especializaciones/<int:pk>/archivo/', ver_especializacion, name='ver_especializacion'),
    path('especializaciones/<int:pk>/resolver/', resolver_especializacion, name='resolver_especializacion'),
    path('especializaciones/<int:pk>/pedir-asignatura/', pedir_asignatura, name='pedir_asignatura'),

    # esta parte es de las rutas CRUD de alumnos
    path('crud/', crud, name='crud'),
    path('alumnos_Add', alumnos_Add, name='alumnos_Add'),
    path('alumnos_del/<int:pk>/', alumnos_del, name='alumnos_del'),
    path('alumnos_findEdit/<int:pk>/', alumnos_findEdit, name='alumnos_findEdit'),
    path('alumnos_Update', alumnos_Update, name='alumnos_Update'),
    path('logout_admin/', logout_admin, name='logout_admin'),
]
