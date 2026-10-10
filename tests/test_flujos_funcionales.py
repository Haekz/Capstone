"""Validaciones funcionales de flujos clave de LBWUS.

La idea no es re-testear cada helper aislado, sino recorrer los caminos que
vive el usuario: registro/login por rol, bloqueo de paneles ajenos, logout,
enlaces principales, estados vacios coherentes y salidas claras en acciones.
"""
from datetime import date, time
from unittest.mock import patch
from django.contrib.auth import get_user_model
User = get_user_model()
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from alumnos.models import Alumno, Clase, Genero, Inscripcion, Profesor, Tutor
