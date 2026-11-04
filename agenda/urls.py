from django.urls import path

from . import views

urlpatterns = [
    path('franjas/agregar/', views.agregar_franja, name='agenda_agregar_franja'),
    path('franjas/<int:pk>/quitar/', views.quitar_franja, name='agenda_quitar_franja'),
    path('reservas/<int:pk>/cancelar/', views.cancelar_clase, name='agenda_cancelar_clase'),
]
