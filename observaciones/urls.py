from django.urls import path

from . import views

urlpatterns = [
    path('<int:id_inscripcion>/guardar/', views.guardar, name='observacion_guardar'),
]
