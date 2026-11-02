from django.urls import path

from . import views, views_alumno

urlpatterns = [
    path('profesor/<int:pk>/enviar/', views.enviar_profesor, name='mensajes_profesor_enviar'),
    path('profesor/abrir/<int:inscripcion_id>/', views.abrir_profesor, name='mensajes_profesor_abrir'),
    path('alumno/<int:pk>/enviar/', views_alumno.enviar_alumno, name='mensajes_alumno_enviar'),
    path('alumno/abrir/<int:profesor_id>/', views_alumno.abrir_alumno, name='mensajes_alumno_abrir'),
]
