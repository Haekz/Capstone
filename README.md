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

Desarrollo y pruebas (incluye las de produccion): pip install -r requirements-dev.txt
Produccion (Railway) instala solo requirements.txt, sin herramientas de desarrollo ni de pruebas.

-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

Pruebas

La base es siempre PostgreSQL (la misma de produccion): reservas, bloqueos y concurrencia solo se validan de verdad ahi.
Sin DATABASE_URL el proyecto no arranca. Django crea y borra una base test_<nombre> en ese servidor: nunca apuntarlo a la base de produccion.

Windows:  set DATABASE_URL=postgresql://usuario:clave@localhost:5432/lbwus& python manage.py test
Linux:    DATABASE_URL=postgresql://usuario:clave@localhost:5432/lbwus python manage.py test
