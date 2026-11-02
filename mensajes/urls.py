from django.urls import path

from . import views

urlpatterns = [
    path('profesor/<int:pk>/enviar/', views.enviar_profesor, name='mensajes_profesor_enviar'),
    path('profesor/abrir/<int:inscripcion_id>/', views.abrir_profesor, name='mensajes_profesor_abrir'),
]
