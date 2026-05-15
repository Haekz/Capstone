
from django.contrib import admin
from django.urls import path, include
from alumnos.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    # Ruta raíz que muestra la página de inicio
    path('', home, name='home'),
    path('alumnos/', include('alumnos.urls')),
    path('admin_portal/', include('admin_portal.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]
