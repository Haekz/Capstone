from django.urls import path

from . import views

urlpatterns = [
    path('registro/', views.registro, name='registro_apoderado'),
    path('confirmar/<str:uidb64>/<str:token>/', views.confirmar_correo, name='apoderado_confirmar_correo'),
    path('mi-cuenta/', views.portal, name='portal_apoderado'),
    path('mi-cuenta/reenviar/', views.reenviar, name='apoderado_reenviar_correo'),
    path('salir/', views.logout_apoderado, name='logout_apoderado'),
    path('revision/', views.revision, name='apoderados_revision'),
    path('<int:id_apoderado>/revisar/', views.revisar, name='apoderado_revisar'),
]
