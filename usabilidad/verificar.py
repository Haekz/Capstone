"""Verificaciones puntuales de hallazgos (10.2)."""
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8765'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
OUT = 'usabilidad/capturas/antes/'

with sync_playwright() as pw:
    nav = pw.chromium.launch(executable_path=EDGE, headless=True)
    for nombre, tam in (('escritorio', {'width': 1366, 'height': 800}), ('movil', {'width': 390, 'height': 844})):
        ctx = nav.new_context(viewport=tam, is_mobile=nombre == 'movil', has_touch=nombre == 'movil')
        p = ctx.new_page()
        p.goto(BASE + '/accounts/login/')
        p.fill('input[name=username]', '11111111-1')
        p.fill('input[name=password]', 'Demo12345!')
        p.click('form[action$="/accounts/login/"] [type=submit]')
        p.wait_for_load_state('networkidle')

        # 1) Buscador: escribir como persona (teclas) vs pegar (evento input)
        caja = p.locator('#dashboard-search-input')
        caja.fill('zzzz')
        p.wait_for_timeout(300)
        pegado = p.locator('#dashboard-teachers-container .teacher-card').count()
        caja.fill('')
        caja.press_sequentially('zzzz', delay=30)
        p.wait_for_timeout(300)
        tecleado = p.locator('#dashboard-teachers-container .teacher-card').count()
        print(f'[{nombre}] tarjetas tras PEGAR "zzzz": {pegado} | tras TECLEAR: {tecleado}')
        caja.fill('')
        caja.press('Backspace')

        # 2) Sidebar: visible y con opciones?
        sb = p.locator('#sidebar-menu')
        print(f'[{nombre}] sidebar visible={sb.is_visible()} items visibles=',
              p.locator('#sidebar-menu a:visible, #sidebar-menu button:visible').count())
        p.screenshot(path=f'{OUT}16b_viewport_{nombre}.png')
        if nombre == 'movil':
            p.click('#hamburger-btn')
            p.wait_for_timeout(500)
            p.screenshot(path=f'{OUT}16c_menu_abierto_movil.png')

        # 3) Ver Horarios: que pasa al tocarlo
        p.goto(BASE + '/alumnos/alumno_home')
        p.locator('.btn-contact-teacher').first.click()
        p.wait_for_timeout(700)
        txt = p.locator('.swal2-popup').all_inner_texts()
        print(f'[{nombre}] Ver Horarios ->', (txt[0][:200].replace(chr(10), ' / ') if txt else 'SIN RESPUESTA VISIBLE'))
        p.screenshot(path=f'{OUT}17b_ver_horarios_{nombre}.png')
        ctx.close()
    nav.close()
