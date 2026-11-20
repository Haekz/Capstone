from django.urls import path

from . import views, views_soporte

urlpatterns = [
    path('franjas/agregar/', views.agregar_franja, name='agenda_agregar_franja'),
    path('franjas/<int:pk>/quitar/', views.quitar_franja, name='agenda_quitar_franja'),
    path('reservas/<int:pk>/cancelar/', views.cancelar_clase, name='agenda_cancelar_clase'),
    # Soporte, desde un ticket de Horario (fase 7)
    path('soporte/<int:id_ticket>/franjas/agregar/', views_soporte.agregar_franja, name='soporte_agregar_franja'),
    path('soporte/<int:id_ticket>/franjas/<int:pk>/quitar/', views_soporte.quitar_franja,
         name='soporte_quitar_franja'),
]
