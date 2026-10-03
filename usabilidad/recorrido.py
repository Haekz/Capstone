"""Recorrido automatizado de usabilidad LBWUS (tarea 10.2).

No reemplaza a usuarios reales: detecta problemas objetivos (errores,
desbordes en movil, controles sin nombre, enlaces rotos, mensajes) y deja
capturas como evidencia. Uso:

    python usabilidad/recorrido.py [--etiqueta antes|despues]

Requiere el servidor de demo en http://127.0.0.1:8765 (levantar_demo.bat).
"""
import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765'
CLAVE = 'Demo12345!'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
AQUI = Path(__file__).parent
VISTAS = {'escritorio': {'width': 1366, 'height': 800}, 'movil': {'width': 390, 'height': 844}}

# Chequeos objetivos que se corren en cada pantalla.
AUDITORIA_JS = r"""
() => {
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const nombre = el => (el.getAttribute('aria-label') || el.getAttribute('title') ||
    el.innerText || el.value || (el.querySelector('img') && el.querySelector('img').alt) || '').trim();
  const desc = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : '');
  const docW = document.documentElement.clientWidth;
  const anchos = [...document.querySelectorAll('body *')].filter(visible)
    .filter(el => el.getBoundingClientRect().right > docW + 2 && !el.closest('[class*="carrito"],[class*="modal"]'))
    .slice(0, 5).map(desc);
  const sinEtiqueta = [...document.querySelectorAll('input,select,textarea')].filter(visible)
    .filter(el => !['hidden','submit','button','checkbox'].includes(el.type))
    .filter(el => !(el.labels && el.labels.length) && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby'))
    .map(el => desc(el) + (el.placeholder ? ' [placeholder="' + el.placeholder + '"]' : ''));
  const sinNombre = [...document.querySelectorAll('a,button')].filter(visible)
    .filter(el => !nombre(el)).map(desc);
  const vacios = [...document.querySelectorAll('a')].filter(visible)
    .filter(a => ['#', '', 'javascript:void(0)'].includes((a.getAttribute('href') || '').trim()) && !a.onclick && !a.getAttribute('onclick'))
    .map(a => desc(a) + ' "' + nombre(a).slice(0, 30) + '"');
  const chicos = [...document.querySelectorAll('a,button,input[type=submit]')].filter(visible)
    .filter(el => { const r = el.getBoundingClientRect(); return r.height < 24 || r.width < 24; })
    .slice(0, 8).map(el => desc(el) + ' "' + nombre(el).slice(0, 20) + '"');
  return {
    titulo: document.title,
    h1: [...document.querySelectorAll('h1')].map(h => h.innerText.trim()).slice(0, 3),
    scrollHorizontal: document.documentElement.scrollWidth > docW + 2,
    anchoDoc: document.documentElement.scrollWidth, anchoVista: docW,
    desbordan: anchos, sinEtiqueta, sinNombre, enlacesVacios: vacios, objetivosChicos: chicos,
    lang: document.documentElement.lang,
  };
}
"""


def login(page, rut):
    page.goto(f'{BASE}/accounts/login/')
    page.fill('input[name=username]', rut)
    page.fill('input[name=password]', CLAVE)
    page.click('form[action$="/accounts/login/"] button[type=submit], form[action$="/accounts/login/"] input[type=submit]')
    page.wait_for_load_state('networkidle')


def logout(ctx):
    ctx.clear_cookies()


# (id, flujo, rol, acciones) ; acciones recibe page y deja la pantalla a capturar.
def pasos():
    def ir(url):
        return lambda p: p.goto(BASE + url)

    def login_error(p):
        p.goto(BASE + '/accounts/login/')
        p.fill('input[name=username]', '11111111-1')
        p.fill('input[name=password]', 'clave-mala')
        p.click('form[action$="/accounts/login/"] [type=submit]')
        p.wait_for_load_state('networkidle')

    def login_vacio(p):
        p.goto(BASE + '/accounts/login/')
        p.click('form[action$="/accounts/login/"] [type=submit]')
        p.wait_for_timeout(400)

    def registro_vacio(p):
        p.goto(BASE + '/alumnos/registro_alumno')
        btn = p.locator('form [type=submit]').first
        btn.click()
        p.wait_for_timeout(800)

    def recuperar(p):
        p.goto(BASE + '/accounts/password_reset/')
        p.fill('input[name=email]', 'ana@demo.cl')
        p.click('form [type=submit]')
        p.wait_for_load_state('networkidle')

    def buscar_profes(p):
        p.goto(BASE + '/alumnos/alumno_home')
        caja = p.locator('#dashboard-search-input')
        if caja.count():
            caja.fill('Matem')
            p.wait_for_timeout(600)

    def buscar_sin_resultado(p):
        p.goto(BASE + '/alumnos/alumno_home')
        caja = p.locator('#dashboard-search-input')
        if caja.count():
            caja.fill('zzzz')
            p.wait_for_timeout(600)

    def portal_ajeno(p):
        p.goto(BASE + '/admin_portal/dashboard/')

    return [
        ('01', 'Navegación general: Inicio', None, ir('/')),
        ('02', 'Navegación general: Nosotros', None, ir('/alumnos/nosotros')),
        ('03', 'Navegación general: Servicios', None, ir('/alumnos/servicios')),
        ('04', 'Navegación general: Planes', None, ir('/alumnos/planes')),
        ('05', 'Navegación general: Contacto', None, ir('/alumnos/contactos')),
        ('06', 'Búsqueda pública: Simulador', None, ir('/alumnos/simulador')),
        ('07', 'Registro: elegir tipo de usuario', None, ir('/alumnos/select')),
        ('08', 'Registro: alumno', None, ir('/alumnos/registro_alumno')),
        ('09', 'Formularios: registro alumno enviado vacío', None, registro_vacio),
        ('10', 'Registro: profesor', None, ir('/profesor/registro_profesor')),
        ('11', 'Inicio de sesión', None, ir('/accounts/login/')),
        ('12', 'Mensajes: login con clave incorrecta', None, login_error),
        ('13', 'Mensajes: login enviado vacío', None, login_vacio),
        ('14', 'Recuperar contraseña', None, recuperar),
        ('15', 'Pago: carrito vacío', None, ir('/alumnos/pago')),
        ('16', 'Mi espacio (alumno)', 'alumno', ir('/alumnos/alumno_home')),
        ('17', 'Búsqueda de profesionales (alumno)', 'alumno', buscar_profes),
        ('18', 'Búsqueda sin resultados (alumno)', 'alumno', buscar_sin_resultado),
        ('19', 'Menú global con sesión de alumno', 'alumno', ir('/')),
        ('20', 'Acceso a portal ajeno (alumno -> admin)', 'alumno', portal_ajeno),
        ('21', 'Cambiar contraseña', 'alumno', ir('/accounts/password_change/')),
        ('22', 'Panel profesor', 'profesor', ir('/profesor/panel')),
        ('23', 'Panel administrador', 'admin', ir('/admin_portal/dashboard/')),
        ('24', 'Administrador: listado de alumnos', 'admin', ir('/admin_portal/crud/')),
    ]


RUT = {'alumno': '11111111-1', 'profesor': '22222222-2', 'admin': '33333333-3'}


def correr(etiqueta):
    salida = AQUI / 'capturas' / etiqueta
    salida.mkdir(parents=True, exist_ok=True)
    resultados = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=EDGE, headless=True)
        for vista, tam in VISTAS.items():
            ctx = nav.new_context(viewport=tam, locale='es-CL',
                                  is_mobile=vista == 'movil', has_touch=vista == 'movil')
            rol_actual = 'inicio'
            for pid, flujo, rol, accion in pasos():
                cambia_rol = rol != rol_actual
                if cambia_rol:
                    logout(ctx)
                    rol_actual = rol
                page = ctx.new_page()
                errores, fallidos, dialogos = [], [], []
                page.on('console', lambda m: m.type == 'error' and errores.append(m.text[:160]))
                page.on('pageerror', lambda e: errores.append('JS: ' + str(e)[:160]))
                page.on('response', lambda r: r.status >= 400 and fallidos.append(f'{r.status} {r.url.replace(BASE, "")}'))
                page.on('dialog', lambda d: (dialogos.append(d.message[:120]), d.dismiss()))
                if rol and cambia_rol:
                    login(page, RUT[rol])
                    errores.clear(); fallidos.clear()
                try:
                    accion(page)
                    page.wait_for_load_state('networkidle')
                    page.wait_for_timeout(500)
                    datos = page.evaluate(AUDITORIA_JS)
                    swal = page.locator('.swal2-popup .swal2-html-container, .swal2-title')
                    mensajes = [t.strip() for t in swal.all_inner_texts() if t.strip()][:3]
                    alertas = [t.strip()[:140] for t in page.locator('.alert, .error, .errorlist, [role=alert], .messages').all_inner_texts() if t.strip()][:3]
                    archivo = f'{pid}_{vista}.png'
                    page.screenshot(path=str(salida / archivo), full_page=True)
                    resultados.append(dict(id=pid, flujo=flujo, rol=rol or 'visitante', vista=vista,
                                           url=page.url.replace(BASE, ''), captura=f'capturas/{etiqueta}/{archivo}',
                                           errores_consola=errores, recursos_fallidos=fallidos,
                                           mensajes=mensajes + alertas + dialogos, **datos))
                except Exception as e:  # el fallo del flujo ES un hallazgo
                    resultados.append(dict(id=pid, flujo=flujo, rol=rol or 'visitante', vista=vista,
                                           fallo=str(e)[:300], errores_consola=errores, recursos_fallidos=fallidos))
                page.close()
            ctx.close()
        nav.close()
    destino = AQUI / f'resultados_{etiqueta}.json'
    destino.write_text(json.dumps(resultados, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(resultados)} pantallas -> {destino}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--etiqueta', default='antes')
    correr(ap.parse_args().etiqueta)
