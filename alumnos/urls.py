from django.urls import path
from django.views.generic import RedirectView

from .views import (
    contactos,
    nosotros,
    planes,
    servicios,
    opcion_user,
    regis_alum,
    alumnos_reg,
    alumno_pag1,
    custom_login,
    logout_alumno,
)
from .reservas import (
    inscribir_clase,
    cancelar_inscripcion,
    reprogramar_inscripcion,
    listar_sesiones_disponibles,
    reservar_sesion,
)
from .webpay import confirmacion, comprar_paquete
from .sala_virtual import sala_virtual, iniciar_directo
from .perfil_profesor import perfil_profesor
from .views_videos import ver_video, videos_alumno

urlpatterns = [
    path('profesores/<int:id_profesor>/', perfil_profesor, name='perfil_profesor'),
    path('sala-virtual/<int:clase_id>/', sala_virtual, name='sala_virtual'),
    path('sala-virtual/<int:clase_id>/iniciar/', iniciar_directo, name='iniciar_directo'),
    # Sitio público
    # El home canónico vive en la raíz ('/') y se registra en lbwus/urls.py.
    # Aquí solo redirigimos para no romper enlaces antiguos a /alumnos/.
    path('', RedirectView.as_view(pattern_name='home', permanent=False), name='alumnos_index'),
    path('contactos', contactos, name='contactos'),
    path('nosotros', nosotros, name='nosotros'),
    path('planes', planes, name='planes'),
    path('servicios', servicios, name='servicios'),
    path('select', opcion_user, name='opcion_user'),

    # Alumno
    path('registro_alumno', regis_alum, name='regis_alum'),
    path('alumnos_reg', alumnos_reg, name='alumnos_reg'),
    path('alumno_home', alumno_pag1, name='alumno_pag1'),
    path('login/', custom_login, name='custom_login_alumno'),
    path('logout_alumno/', logout_alumno, name='logout_alumno'),

    # Funcionalidades del alumno
    path('inscribir_clase/', inscribir_clase, name='inscribir_clase'),
    path('sesiones-disponibles/', listar_sesiones_disponibles, name='sesiones_disponibles'),
    path('reservar-sesion/', reservar_sesion, name='reservar_sesion'),
    path(
        'cancelar_inscripcion/<int:pk>/',
        cancelar_inscripcion,
        name='cancelar_inscripcion'
    ),
    path('reprogramar_inscripcion/<int:pk>/', reprogramar_inscripcion, name='reprogramar_inscripcion'),

    # Pago / Transbank
    path('confirmacion', confirmacion, name='confirmacion'),
    path('comprar-paquete/', comprar_paquete, name='comprar_paquete'),

    # Videos que el profesor le compartió (agregado de videos)
    path('mis-videos/', videos_alumno, name='videos_alumno'),
    path('mis-videos/<str:video_id>/ver/', ver_video, name='ver_video'),
]
