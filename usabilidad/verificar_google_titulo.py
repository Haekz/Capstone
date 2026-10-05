"""Recorrido visual de Google (codigo + completar) y titulo del profesor.

Requiere la demo en 127.0.0.1:8767 con usabilidad.settings_usab.
Uso: python usabilidad/verificar_google_titulo.py
"""
import os
import sys
from datetime import date
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'usabilidad.settings_usab')
django.setup()

from allauth.account.models import EmailAddress  # noqa: E402
from allauth.socialaccount.adapter import get_adapter  # noqa: E402
from allauth.socialaccount.models import SocialAccount, SocialLogin  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.sessions.backends.db import SessionStore  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from alumnos import codigo_google  # noqa: E402
from alumnos.models import Genero, Profesor  # noqa: E402

BASE = 'http://127.0.0.1:8767'
OUT = Path(__file__).parent / 'capturas' / 'google_titulo'
OUT.mkdir(parents=True, exist_ok=True)
User = get_user_model()
PDF = OUT / 'titulo_demo.pdf'
PDF.write_bytes(b'%PDF-1.4\n% titulo demo\n')


def sesion_google(verificado):
    from allauth.socialaccount.models import SocialApp
    from django.contrib.sites.models import Site
    app, _ = SocialApp.objects.get_or_create(provider='google', defaults=dict(name='Google', client_id='x', secret='y'))
    app.sites.add(Site.objects.get_current())
    correo = 'gabi.nueva@demo.cl'
    sl = SocialLogin(
        account=SocialAccount(provider='google', uid='demo-1', extra_data={'email': correo, 'name': 'Gabi Nueva'}),
        user=User(email=correo), provider=get_adapter().get_provider(None, 'google'),
        email_addresses=[EmailAddress(email=correo, verified=True, primary=True)])
    s = SessionStore()
    s[codigo_google.CLAVE] = {'correo': correo, 'nombre': 'Gabi Nueva', 'sociallogin': sl.serialize(),
                              'verificado': verificado, 'codigo': 'x', 'vence': 9e12, 'intentos': 0, 'enviado': 0}
    s.create()
    return s.session_key


def profesor_pendiente():
    g = Genero.objects.first()
    u, _ = User.objects.get_or_create(username='15555555-6', defaults=dict(rut='15555555-6', rol='profesor'))
    u.set_password('Demo12345!')
    u.save()
    p, _ = Profesor.objects.get_or_create(user=u, defaults=dict(
        nombre='Paula Pendiente', rut='15555555-6', especialidad='Química', direccion='Santiago',
        fecha_nacimiento=date(1990, 1, 1), correo_electronico='paula@demo.cl', telefono='933333333', genero=g))
    p.titulo_estado = Profesor.TITULO_PENDIENTE
    p.titulo_archivo = ''
    p.save()


def login(page, rut):
    page.goto(f'{BASE}/accounts/login/')
    page.fill('#id_username', rut)
    page.fill('#id_password', 'Demo12345!')
    page.click('button[type=submit]')
    page.wait_for_load_state('networkidle')


resultados = []


def ok(nombre, condicion):
    resultados.append((nombre, bool(condicion)))
    print(('OK   ' if condicion else 'FAIL ') + nombre)


profesor_pendiente()
# El ORM no se puede usar dentro del loop de Playwright: sesiones listas antes.
VIEWPORTS = (('desktop', {'width': 1366, 'height': 900}), ('movil', {'width': 390, 'height': 844}))
SESIONES = {(e, v): sesion_google(v) for e, _ in VIEWPORTS for v in (False, True)}

with sync_playwright() as pw:
    # Proxy corporativo para los CDN (SweetAlert, fuentes); la demo local va directo.
    nav = pw.chromium.launch(proxy={'server': 'http://sysproxy.wal-mart.com:8080',
                                    'bypass': '127.0.0.1,localhost'})
    for etiqueta, vp in VIEWPORTS:
        ctx = nav.new_context(viewport=vp)
        ctx.add_cookies([{'name': 'sessionid', 'value': SESIONES[(etiqueta, False)], 'url': BASE}])
        page = ctx.new_page()
        page.goto(f'{BASE}/accounts/google/verificar/')
        ok(f'{etiqueta}: pantalla codigo', page.locator('#codigo').is_visible())
        page.screenshot(path=OUT / f'{etiqueta}_1_codigo.png', full_page=True)
        ctx.close()

        ctx = nav.new_context(viewport=vp)
        ctx.add_cookies([{'name': 'sessionid', 'value': SESIONES[(etiqueta, True)], 'url': BASE}])
        page = ctx.new_page()
        page.goto(f'{BASE}/accounts/google/completar/')
        page.check('input[value=profesor]')
        ok(f'{etiqueta}: especialidad visible si profesor', page.locator('#id_especialidad').is_visible())
        ok(f'{etiqueta}: nivel oculto si profesor', not page.locator('#id_nivel_educacion').is_visible())
        page.screenshot(path=OUT / f'{etiqueta}_2_completar.png', full_page=True)
        ctx.close()

    ctx = nav.new_context(viewport={'width': 1366, 'height': 900})
    page = ctx.new_page()
    page.on('dialog', lambda d: d.accept())
    login(page, '15555555-6')
    page.evaluate("localStorage.setItem('prof_active_tab','inicio')")
    page.goto(f'{BASE}/profesor/panel')
    page.wait_for_timeout(600)  # profFadeIn dura 0.4 s: sin esto la captura sale desteñida
    ok('profesor: aviso subir titulo', page.get_by_text('Sube tu título profesional').is_visible())
    page.screenshot(path=OUT / 'desktop_3_panel_sin_titulo.png')
    page.set_input_files('#titulo-archivo', str(PDF))
    page.click('#form-titulo button')
    page.wait_for_selector('.swal2-popup', timeout=15000)
    ok('profesor: subida OK', 'Recibido' in page.inner_text('.swal2-popup'))
    page.click('.swal2-confirm')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(600)
    ok('profesor: queda en revision', page.get_by_text('Tu título está en revisión').is_visible())
    page.screenshot(path=OUT / 'desktop_4_panel_en_revision.png')
    ctx.close()

    ctx = nav.new_context(viewport={'width': 1366, 'height': 900})
    page = ctx.new_page()
    login(page, '33333333-3')
    page.goto(f'{BASE}/admin_portal/titulos/')
    ok('admin: ve pendiente', page.get_by_text('Paula Pendiente').first.is_visible())
    page.screenshot(path=OUT / 'desktop_5_admin_titulos.png', full_page=True)
    page.click('button[value=aprobar]')
    page.wait_for_load_state('networkidle')
    ok('admin: aprobado', 'aprobado' in page.content())
    page.screenshot(path=OUT / 'desktop_6_admin_aprobado.png', full_page=True)
    ctx.close()
    nav.close()

fallas = [n for n, b in resultados if not b]
print(f'\n{len(resultados) - len(fallas)}/{len(resultados)} OK')
sys.exit(1 if fallas else 0)
