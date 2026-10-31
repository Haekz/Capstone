🎓 LBWUS — Learn Better With Us

Una plataforma de auto-aprendizaje colaborativo donde profesores y estudiantes se encuentran para enseñar, aprender y crecer juntos.

-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

📖 ¿Qué es LBWUS?

LBWUS es una aplicación web de auto-aprendizaje desarrollada como proyecto universitario. 
Está pensada para construir una comunidad educativa inclusiva donde tanto profesores como estudiantes pueden unirse para compartir conocimiento, 
acceder a clases y ser parte de una comunidad que cree en el aprendizaje continuo.

✨ Funcionalidades

👨‍🎓 Registro e inicio de sesión para alumnos y profesores

🏫 Portal de administración para gestión de usuarios

📋 Registro y gestión de alumnos

🔐 Sistema de autenticación con roles diferenciados

📱 Interfaz web responsiva

-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

🛠️ Tecnologías utilizadas

Python 3.13 Lenguaje principal | Django 5.0.6 Framework web | PostgreSQLBase de datos en producción | Gunicorn Servidor WSGI | Whitenoise Archivos estáticos | Railway Plataforma de despliegue | 

-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

🚀 Instalación local

Prerrequisitos

Python 3.13+
pip
Git

-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Pruebas

Rapidas (SQLite local): python manage.py test

Contra PostgreSQL, la base de produccion (reservas, bloqueos y concurrencia se validan de verdad solo aqui).
EXIGIR_POSTGRES=1 detiene la ejecucion si falta DATABASE_URL, en vez de caer en SQLite sin avisar:

Windows:  set EXIGIR_POSTGRES=1& set DATABASE_URL=postgresql://usuario:clave@localhost:5432/lbwus& python manage.py test
Linux:    EXIGIR_POSTGRES=1 DATABASE_URL=postgresql://usuario:clave@localhost:5432/lbwus python manage.py test
