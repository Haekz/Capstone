from django.urls import path

from . import views

urlpatterns = [
    path('registro/', views.registro, name='registro_apoderado'),
    path('confirmar/<str:uidb64>/<str:token>/', views.confirmar_correo, name='apoderado_confirmar_correo'),
    path('mi-cuenta/', views.portal, name='portal_apoderado'),
    path('mi-cuenta/reenviar/', views.reenviar, name='apoderado_reenviar_correo'),
    path('mi-cuenta/estudiantes/nuevo/', views.registrar_estudiante, name='apoderado_registrar_estudiante'),
    path('mi-cuenta/estudiantes/<int:id_vinculo>/clave/', views.clave_estudiante, name='apoderado_clave_estudiante'),
    path('mi-cuenta/estudiantes/<int:id_vinculo>/revocar/', views.revocar_vinculo, name='apoderado_revocar_vinculo'),
    path('estudiante/nueva-clave/', views.nueva_clave_estudiante, name='nueva_clave_estudiante'),
    path('mi-cuenta/estudiantes/<int:id_vinculo>/comprar/', views.comprar_paquete, name='apoderado_comprar_paquete'),
    path('mi-cuenta/estudiantes/<int:id_vinculo>/clases/', views.clases_estudiante, name='apoderado_clases_estudiante'),
    path('mi-cuenta/estudiantes/<int:id_vinculo>/clases/reservar/', views.reservar_clase,
         name='apoderado_reservar_clase'),
    path('mi-cuenta/estudiantes/<int:id_vinculo>/clases/<int:id_inscripcion>/cancelar/', views.cancelar_clase,
         name='apoderado_cancelar_clase'),
    path('mi-cuenta/estudiantes/<int:id_vinculo>/clases/<int:id_inscripcion>/reprogramar/', views.reprogramar_clase,
         name='apoderado_reprogramar_clase'),
    path('invitacion/<str:token>/', views.invitacion, name='apoderado_invitacion'),
    # Adolescentes de 14 a 17 (fase 1b-ii): su cuenta es de alumno, restringida.
    path('estudiantes/registro/', views.registro_adolescente, name='adolescente_registro'),
    path('estudiantes/confirmar/<str:uidb64>/<str:token>/', views.confirmar_correo_adolescente,
         name='adolescente_confirmar_correo'),
    path('estudiantes/mi-solicitud/', views.solicitud_adolescente, name='adolescente_solicitud'),
    path('estudiantes/mi-solicitud/reenviar/', views.reenviar_correo_adolescente, name='adolescente_reenviar_correo'),
    path('estudiantes/mi-solicitud/invitar/', views.invitar, name='adolescente_invitar'),
    path('salir/', views.logout_apoderado, name='logout_apoderado'),
    path('revision/', views.revision, name='apoderados_revision'),
    path('revision/documentos/<int:id_documento>/', views.ver_documento, name='apoderado_documento'),
    path('revision/vinculos/<int:id_vinculo>/revocar/', views.revocar_vinculo_admin, name='apoderados_revocar_vinculo'),
    path('<int:id_apoderado>/revisar/', views.revisar, name='apoderado_revisar'),
    path('vinculos/<int:id_vinculo>/revisar/', views.revisar_vinculo, name='apoderado_revisar_vinculo'),
]
