from django.urls import path

from . import views

urlpatterns = [
    path('', views.mis_notificaciones, name='mis_notificaciones'),
]
