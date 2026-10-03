@echo off
REM Levanta LBWUS con datos de demo para pruebas de usabilidad (10.2).
REM Usa una base aparte (usab.sqlite3): la db.sqlite3 real NO se toca.
cd /d "%~dp0.."
set DJANGO_SETTINGS_MODULE=usabilidad.settings_usab
set PY=..\Capstone\.venv-win\Scripts\python.exe
"%PY%" manage.py migrate --noinput || exit /b 1
"%PY%" manage.py shell -c "exec(open('usabilidad/seed.py', encoding='utf-8').read())" || exit /b 1
echo.
echo  Usuarios demo (clave: Demo12345!)
echo    Alumno   11111111-1
echo    Profesor 22222222-2
echo    Admin    33333333-3
echo.
if "%1"=="--solo-datos" exit /b 0
"%PY%" manage.py runserver 127.0.0.1:8765
