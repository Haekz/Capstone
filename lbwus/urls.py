
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from alumnos.views import home, custom_login

urlpatterns = [
    path('admin/', admin.site.urls),
    # Ruta raíz que muestra la página de inicio
    path('', home, name='home'),
    path('alumnos/', include('alumnos.urls')),
    path('admin_portal/', include('admin_portal.urls')),
    path('profesor/', include('user_profesor.urls')),
    path('accounts/login/', custom_login, name='login'),
    path('accounts/password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/recuperar_formulario.html'), name='password_reset'),
    path('accounts/password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/recuperar_enviado.html'), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/recuperar_confirmar.html'), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/recuperar_completado.html'), name='password_reset_complete'),
    path('accounts/', include('django.contrib.auth.urls')),
]
