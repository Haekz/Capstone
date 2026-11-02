from django.urls import path

from . import views, views_alumno, views_apoderado, views_reporte, views_revision

urlpatterns = [
    path('profesor/<int:pk>/enviar/', views.enviar_profesor, name='mensajes_profesor_enviar'),
    path('profesor/abrir/<int:inscripcion_id>/', views.abrir_profesor, name='mensajes_profesor_abrir'),
    path('alumno/<int:pk>/enviar/', views_alumno.enviar_alumno, name='mensajes_alumno_enviar'),
    path('alumno/abrir/<int:profesor_id>/', views_alumno.abrir_alumno, name='mensajes_alumno_abrir'),
    path('apoderado/', views_apoderado.buzon_apoderado, name='mensajes_apoderado'),
    path('apoderado/<int:pk>/enviar/', views_apoderado.enviar_apoderado, name='mensajes_apoderado_enviar'),
    path('apoderado/abrir/<int:id_vinculo>/<int:profesor_id>/', views_apoderado.abrir_apoderado,
         name='mensajes_apoderado_abrir'),
    path('reportar/<int:pk>/', views_reporte.reportar_conversacion, name='mensajes_reportar'),
    path('soporte/ticket/<int:id_ticket>/', views_reporte.leer_conversacion, name='mensajes_soporte_leer'),
    path('soporte/revision/', views_revision.revision_lista, name='mensajes_revision'),
    path('soporte/revision/<int:pk>/', views_revision.revision_detalle, name='mensajes_revision_detalle'),
]
