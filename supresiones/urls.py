from django.urls import path

from . import views, views_soporte

urlpatterns = [
    path('eliminar-cuenta/', views.eliminar_cuenta, name='eliminar_cuenta'),
    path('eliminar-cuenta/confirmar/<str:token>/', views.confirmar, name='confirmar_eliminar_cuenta'),
    path('soporte/<int:id_ticket>/ejecutar/', views_soporte.ejecutar, name='supresion_ejecutar'),
    path('soporte/<int:id_ticket>/rechazar/', views_soporte.rechazar, name='supresion_rechazar'),
]
