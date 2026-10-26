from django.urls import path

from . import views

urlpatterns = [
    path('calificar/<int:id_inscripcion>/', views.calificar, name='resena_calificar'),
    path('<int:id_resena>/reportar/', views.reportar_como_alumno, name='resena_reportar_alumno'),
    path('<int:id_resena>/reportar-profesor/', views.reportar_como_profesor, name='resena_reportar_profesor'),
    path('mis-resenas/', views.resenas_profesor, name='resenas_profesor'),
    path('moderacion/', views.moderacion, name='resenas_moderacion'),
    path('<int:id_resena>/moderar/', views.moderar, name='resena_moderar'),
]
