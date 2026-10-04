
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.decorators.cache import never_cache
from alumnos.views import home, custom_login
from alumnos import google_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Ruta raíz que muestra la página de inicio.
    # Este es el UNICO lugar donde se registra name='home'.
    # No volver a declararlo en las urls de las apps: Django permite nombres
    # duplicados sin avisar y el ultimo registrado gana el reverse().
    path('', home, name='home'),
    path('alumnos/', include('alumnos.urls')),
    path('admin_portal/', include('admin_portal.urls')),
    path('profesor/', include('user_profesor.urls')),
    path('accounts/login/', custom_login, name='login'),
path(
    'accounts/password_reset/',
    auth_views.PasswordResetView.as_view(
        template_name='registration/recuperar_formulario.html',
        email_template_name='registration/correo_recuperacion_clave.txt',
        html_email_template_name='registration/correo_recuperacion_clave.html',
        subject_template_name='registration/asunto_recuperacion_clave.txt',
    ),
    name='password_reset'
),
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/recuperar_enviado.html'), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/recuperar_confirmar.html'), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/recuperar_completado.html'), name='password_reset_complete'),
    # Cambiar contrasena con la sesion iniciada (menu de cuenta del navbar).
    # Se declaran antes del include de django.contrib.auth.urls para usar
    # nuestras plantillas y no las del admin de Django.
    path('accounts/password_change/', never_cache(auth_views.PasswordChangeView.as_view(template_name='registration/cambiar_clave.html')), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/cambiar_clave_listo.html'), name='password_change_done'),
    path('accounts/', include('django.contrib.auth.urls')),
    # Registro con Google: codigo por correo y datos faltantes (antes de allauth).
    path('accounts/google/verificar/', google_views.google_verificar, name='google_verificar'),
    path('accounts/google/reenviar/', google_views.google_reenviar, name='google_reenviar'),
    path('accounts/google/completar/', google_views.google_completar, name='google_completar'),
    path("accounts/", include("allauth.urls")),
]
