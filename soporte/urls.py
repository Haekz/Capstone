from django.urls import path

from . import reportes, views

urlpatterns = [
    path('', views.panel, name='panel_soporte'),
    path('tickets/<int:id_ticket>/', reportes.ver_reporte, name='soporte_reporte'),
    path('tickets/<int:id_ticket>/reasignar/', views.reasignar_ticket, name='soporte_reasignar'),
    path('mis-tickets/', reportes.mis_tickets, name='mis_tickets'),
    path('mis-tickets/nuevo/', reportes.nuevo_ticket, name='nuevo_ticket'),
    path('mis-tickets/<int:id_ticket>/', reportes.mi_ticket, name='mi_ticket'),
    path('salir/', views.logout_soporte, name='logout_soporte'),
]
