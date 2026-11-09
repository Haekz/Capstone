from django.urls import path
from .views import logout_prof, regis_prof, regis_tutor, panel_profesor, actualizar_perfil_prof, solicitar_retiro, subir_titulo, foto_profesor, guardar_cuenta_bancaria, confirmar_cambio_cuenta, guardar_frecuencia_pago
from .views_especializaciones import subir_especializacion
from .views_videos import eliminar_video, subir_video, videos_profesor

urlpatterns = [
    path('registro_profesor', regis_prof, name='regis_prof'),
    path('registro_tutor', regis_tutor, name='regis_tutor'),
    path('panel', panel_profesor, name='panel_profesor'),
    path('actualizar_perfil', actualizar_perfil_prof, name='actualizar_perfil_prof'),
    path('solicitar_retiro', solicitar_retiro, name='solicitar_retiro'),
    path('cuenta_bancaria', guardar_cuenta_bancaria, name='guardar_cuenta_bancaria'),
    path('cuenta_bancaria/confirmar/<str:token>', confirmar_cambio_cuenta, name='confirmar_cambio_cuenta'),
    path('frecuencia_pago', guardar_frecuencia_pago, name='guardar_frecuencia_pago'),
    path('logout', logout_prof, name='logout_prof'),
    path('subir_titulo', subir_titulo, name='subir_titulo'),
    path('subir_especializacion', subir_especializacion, name='subir_especializacion'),
    path('foto/<int:id_profesor>', foto_profesor, name='foto_profesor'),
    path('videos', videos_profesor, name='videos_profesor'),
    path('videos/subir', subir_video, name='subir_video'),
    path('videos/<str:video_id>/eliminar', eliminar_video, name='eliminar_video'),
]
