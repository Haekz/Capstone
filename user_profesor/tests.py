"""Tests del panel del profesor y del acceso de administrador.

Cubren tres bugs verificados explotandolos antes de corregirlos:

1. custom_login() y login_admin() podian dejar la sesion apuntando a un
   perfil Tutor ajeno (Tutor.objects.first()) o a un user.id que no es un
   id_tutor.
2. El panel regalaba $45.000/$36.000 a las cuentas sin inscripciones, y
   solicitar_retiro() dejaba retirar ese dinero inexistente.
3. El grafico de rendimiento rellenaba los meses vacios con [14, 22, 18,
   25, 32] en vez de mostrar 0.
"""
from datetime import date, time
from django.contrib.auth import get_user_model
User = get_user_model()
from django.test import TestCase
from django.urls import reverse
from alumnos.models import Alumno, Clase, Genero, Inscripcion, Profesor, SolicitudRetiro, Tutor
from user_profesor.views import PAGO_PROFESOR, VALOR_INSCRIPCION, calcular_saldos