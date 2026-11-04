from django.urls import path

from . import views

urlpatterns = [
    path('', views.lista, name='requerimientos'),
    path('nuevo/', views.nuevo, name='requerimiento_nuevo'),
    path('<int:pk>/', views.detalle, name='requerimiento_detalle'),
    path('<int:pk>/<str:nombre>/', views.accion, name='requerimiento_accion'),
]
