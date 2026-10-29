from django.urls import path

from . import views

urlpatterns = [
    path('', views.panel, name='panel_soporte'),
    path('tickets/<int:id_ticket>/reasignar/', views.reasignar_ticket, name='soporte_reasignar'),
    path('salir/', views.logout_soporte, name='logout_soporte'),
]
