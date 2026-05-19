from django.urls import path
from .views import regis_prof, regis_tutor

urlpatterns = [
    path('registro_profesor', regis_prof, name='regis_prof'),
    path('registro_tutor', regis_tutor, name='regis_tutor'),
]
