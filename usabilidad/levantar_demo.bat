@echo off
REM Levanta LBWUS con las cuentas de demo para pruebas de usabilidad (10.2).
REM Usa una base PostgreSQL aparte (USAB_DATABASE_URL): la base real NO se toca.
REM Ejemplo: set USAB_DATABASE_URL=postgresql://usuario:clave@localhost:5432/lbwus_usab
REM La clave de las cuentas demo va en CUENTAS_DEMO_CLAVE (no se guarda en el codigo).
REM PY: el python a usar (por defecto, el del PATH).
if "%USAB_DATABASE_URL%"=="" (
  echo Falta USAB_DATABASE_URL con una base PostgreSQL aparte para la demo.
  exit /b 1
)
if "%CUENTAS_DEMO_CLAVE%"=="" (
  echo Falta CUENTAS_DEMO_CLAVE con la clave de las cuentas demo.
  exit /b 1
)
cd /d "%~dp0.."
set DJANGO_SETTINGS_MODULE=usabilidad.settings_usab
if "%PY%"=="" set PY=python
"%PY%" manage.py migrate --noinput || exit /b 1
"%PY%" manage.py crear_cuentas_demo || exit /b 1
if "%1"=="--solo-datos" exit /b 0
"%PY%" manage.py runserver 127.0.0.1:8765
