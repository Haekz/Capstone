"""Genera usabilidad/REGISTRO_USABILIDAD.html (tarea 10.2).

Los hallazgos se escriben aqui a mano (son juicio de quien prueba); el
script solo arma la pagina con las capturas antes/despues. Para agregar lo
que digan los usuarios reales, sumar entradas a HALLAZGOS con
origen='Usuario' y volver a ejecutar:  python usabilidad/generar_registro.py
"""
import html
import json
from datetime import date
from pathlib import Path

AQUI = Path(__file__).parent

# estado: 'Corregido' | 'Pendiente'   severidad: 'Alta' | 'Media' | 'Baja'
HALLAZGOS = [
    dict(id='H01', flujo='Búsqueda de profesionales (Mi espacio)', origen='Recorrido guiado', severidad='Alta',
         dificultad='Al pegar un texto o usar el autocompletado del teclado móvil, la lista no se filtra.',
         confuso='El buscador muestra "zzzz" pero siguen apareciendo todos los profesores: parece que no existe la búsqueda.',
         error='El filtro escuchaba solo "keyup" (teclas físicas); pegar, autocompletar o la "x" de borrar no lo disparaban.',
         sugerencia='Filtrar con cualquier cambio del campo.',
         estado='Corregido', correccion='Evento "input" en vez de "keyup"; campo tipo search con nombre accesible (aria-label).',
         antes='antes/18_escritorio.png', despues='despues/18_viewport_escritorio.png'),
    dict(id='H02', flujo='Acceso a Mi espacio', origen='Recorrido guiado', severidad='Alta',
         dificultad='Las tarjetas de resumen muestran "12 hrs", "2 Pendientes" y "4.9" a una alumna recién creada.',
         confuso='El usuario cree que hay tutorías agendadas que no existen.',
         error='Números escritos a mano en la plantilla, no salían de la base de datos.',
         sugerencia='Mostrar solo datos reales.',
         estado='Corregido', correccion='Ahora muestran clases inscritas, clases disponibles y profesores disponibles, con datos reales.',
         antes='antes/16_escritorio.png', despues='despues/16_escritorio.png'),
    dict(id='H03', flujo='Búsqueda pública (Simulador)', origen='Recorrido guiado', severidad='Alta',
         dificultad='En móvil y escritorio desaparece el menú del sitio; el título "Conversión de Moneda" queda pegado arriba.',
         confuso='No hay forma de volver al inicio ni de navegar desde esa página.',
         error='Los títulos usaban la clase "header", que es la del navbar fijo: se convertían en barras fijas encima del menú.',
         sugerencia='No reutilizar clases globales en una página.',
         estado='Corregido', correccion='Clase propia "sim-header" y título principal como h1.',
         antes='antes/06_movil.png', despues='despues/06_movil.png'),
    dict(id='H04', flujo='Formularios (Simulador)', origen='Recorrido guiado', severidad='Media',
         dificultad='Las etiquetas "Monto:", "De:" y "A:" tienen borde redondeado igual que los campos.',
         confuso='Parecen campos para escribir; el usuario intenta tocarlas.',
         error='El CSS aplicaba el estilo de input también a .form-label.',
         sugerencia='Etiquetas como texto, alineadas a la izquierda.',
         estado='Corregido', correccion='Estilo propio para las etiquetas.',
         antes='antes/06_movil.png', despues='despues/06_movil.png'),
    dict(id='H05', flujo='Registro de alumno (Formularios)', origen='Recorrido guiado', severidad='Media',
         dificultad='"Nivel de Educación" y "Género" muestran "---------".',
         confuso='No queda claro si hay que elegir algo ni qué.',
         error='Opción vacía por defecto de Django sin texto.',
         sugerencia='Texto guía en la opción vacía.',
         estado='Corregido', correccion='"Selecciona tu nivel" y "Selecciona tu género".',
         antes='antes/08_escritorio.png', despues='despues/08_escritorio.png'),
    dict(id='H06', flujo='Acceso a Mi espacio (móvil)', origen='Recorrido guiado', severidad='Media',
         dificultad='En el primer ingreso se abre solo el modal "Temas de Interés" y tapa el panel.',
         confuso='La alumna llega y lo primero es una ventana que no pidió.',
         error='Apertura automática a los 800 ms del primer login.',
         sugerencia='Mostrarlo como sugerencia dentro del panel, no como ventana bloqueante.',
         estado='Pendiente', correccion='Decisión de diseño del equipo: se deja documentado.',
         antes='antes/16b_viewport_movil.png', despues=''),
    dict(id='H07', flujo='Visualización de perfiles', origen='Recorrido guiado', severidad='Media',
         dificultad='No existe una página de perfil del profesional; "Ver Horarios" lleva al catálogo general de clases.',
         confuso='Se espera ver los horarios de ESE profesor y aparecen todas las clases.',
         error='Funcionalidad no implementada.',
         sugerencia='Página o modal de perfil con especialidad, clases y horarios del profesor.',
         estado='Pendiente', correccion='Requiere desarrollo (vista + plantilla).',
         antes='antes/17b_ver_horarios_escritorio.png', despues=''),
    dict(id='H08', flujo='Búsqueda de profesionales', origen='Recorrido guiado', severidad='Media',
         dificultad='Todos los profesores aparecen a "1.2 km" y con nota "5.0".',
         confuso='Parece un dato real de cercanía y calificación.',
         error='Valores fijos en la plantilla; la pestaña "Tutores" y los videos son de ejemplo, no de la base.',
         sugerencia='Ocultar distancia y nota hasta tener datos reales.',
         estado='Pendiente', correccion='Requiere definir de dónde salen distancia y calificación.',
         antes='antes/16_movil.png', despues=''),
    dict(id='H09', flujo='Búsqueda pública (Simulador)', origen='Recorrido guiado', severidad='Media',
         dificultad='Los profesores del simulador (Juan Pérez, María Gómez…) no existen en el sistema.',
         confuso='Un visitante busca y encuentra gente que después no está.',
         error='Lista fija en el JavaScript de la página.',
         sugerencia='Consultar los profesores reales o rotular claramente "Ejemplo".',
         estado='Pendiente', correccion='Requiere un endpoint con los profesores.',
         antes='antes/06_escritorio.png', despues=''),
    dict(id='H10', flujo='Panel administrador', origen='Recorrido guiado', severidad='Baja',
         dificultad='El gráfico "Crecimiento y Actividad" muestra Feb–Jun con una curva subiendo.',
         confuso='Los meses no son los actuales y la curva no corresponde a los datos.',
         error='Gráfico SVG dibujado a mano en la plantilla.',
         sugerencia='Calcularlo con los registros reales o quitarlo.',
         estado='Pendiente', correccion='',
         antes='antes/23_movil.png', despues=''),
    dict(id='H11', flujo='Panel profesor', origen='Recorrido guiado', severidad='Baja',
         dificultad='"Clases de Hoy" muestra la clase todos los días y "Clases Disponibles Restantes" usa un tope fijo de 8.',
         confuso='El profesor no sabe si la clase es realmente hoy.',
         error='La vista no filtra por fecha.',
         sugerencia='Filtrar por día o renombrar a "Mis clases".',
         estado='Pendiente', correccion='',
         antes='antes/22_movil.png', despues=''),
    dict(id='H12', flujo='Registro de alumno (Botones y enlaces)', origen='Recorrido guiado', severidad='Baja',
         dificultad='"Inicia sesión aquí" es un enlace de menos de 24 px de alto.',
         confuso='Difícil de tocar con el dedo en móvil.',
         error='Objetivo táctil bajo el mínimo de WCAG 2.2 (2.5.8).',
         sugerencia='Aumentar el área tocable.',
         estado='Pendiente', correccion='',
         antes='antes/08_movil.png', despues=''),
    dict(id='H13', flujo='Pie de página (todas)', origen='Recorrido guiado', severidad='Baja',
         dificultad='Contacto con dirección "Vernon Rockville, CT 06066" y teléfono "123-456-7890".',
         confuso='Datos de plantilla: restan credibilidad.',
         error='Texto de ejemplo no reemplazado.',
         sugerencia='Poner datos reales del proyecto.',
         estado='Pendiente', correccion='',
         antes='antes/07_movil.png', despues=''),
]

# Lo que SI funciono bien (tambien es resultado de la prueba).
FORTALEZAS = [
    'Login: el error de credenciales es claro y visible ("RUT/Correo o contraseña incorrectos").',
    'Cada rol entra directo a su portal y no puede abrir el de otro (tarea 6.6).',
    'Elegir tipo de cuenta (Alumno / Profesor) es claro y bien jerarquizado.',
    'Recuperar contraseña lleva a una confirmación entendible.',
    'Ninguna de las 48 pantallas tiene errores de JavaScript, recursos rotos ni scroll horizontal en móvil.',
]


def tabla_flujos():
    datos = json.loads((AQUI / 'resultados_despues.json').read_text(encoding='utf-8'))
    filas = {}
    for r in datos:
        f = filas.setdefault(r['id'], dict(flujo=r['flujo'], rol=r['rol'], vistas=[]))
        f['vistas'].append(r['vista'] + (' (falló)' if r.get('fallo') else ' (ok)'))
    return ''.join(
        f"<tr><td>{k}</td><td>{html.escape(v['flujo'])}</td><td>{v['rol']}</td><td>{' · '.join(v['vistas'])}</td></tr>"
        for k, v in sorted(filas.items()))


def img(ruta, etiqueta):
    if not ruta:
        return f'<div class="sin">{etiqueta}: sin captura (pendiente)</div>'
    return (f'<figure><figcaption>{etiqueta}</figcaption>'
            f'<a href="capturas/{ruta}" target="_blank"><img loading="lazy" src="capturas/{ruta}" alt="{etiqueta}: {ruta}"></a></figure>')


def tarjeta(h):
    color = {'Corregido': 'ok', 'Pendiente': 'pend'}[h['estado']]
    campos = [('Dificultad del usuario', 'dificultad'), ('Qué resultó confuso', 'confuso'),
              ('Error detectado', 'error'), ('Sugerencia', 'sugerencia'), ('Corrección', 'correccion')]
    dl = ''.join(f'<dt>{t}</dt><dd>{html.escape(h[k]) or "—"}</dd>' for t, k in campos)
    return f'''<article class="h" id="{h['id']}">
<header><span class="id">{h['id']}</span><h3>{html.escape(h['flujo'])}</h3>
<span class="tag sev-{h['severidad'].lower()}">{h['severidad']}</span><span class="tag {color}">{h['estado']}</span>
<span class="tag org">{h['origen']}</span></header>
<dl>{dl}</dl><div class="imgs">{img(h['antes'], 'Antes')}{img(h['despues'], 'Después')}</div></article>'''


def generar():
    total = len(HALLAZGOS)
    corr = sum(h['estado'] == 'Corregido' for h in HALLAZGOS)
    altas = sum(h['severidad'] == 'Alta' for h in HALLAZGOS)
    altas_ok = sum(h['severidad'] == 'Alta' and h['estado'] == 'Corregido' for h in HALLAZGOS)
    filas = ''.join(
        f"<tr><td><a href='#{h['id']}'>{h['id']}</a></td><td>{html.escape(h['flujo'])}</td>"
        f"<td>{h['severidad']}</td><td>{h['estado']}</td></tr>" for h in HALLAZGOS)
    fort = ''.join(f'<li>{html.escape(f)}</li>' for f in FORTALEZAS)
    pagina = f'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registro de pruebas de usabilidad — LBWUS (10.2)</title>
<style>
:root{{--p:#6d28d9;--t:#1f1a2e;--m:#5b5670;--b:#e7e3f0}}
*{{box-sizing:border-box}}body{{font-family:system-ui,Segoe UI,sans-serif;color:var(--t);margin:0;background:#f7f5fb;line-height:1.5}}
main{{max-width:1100px;margin:auto;padding:24px}}h1{{color:var(--p);margin-bottom:4px}}h2{{margin-top:40px;border-bottom:2px solid var(--b);padding-bottom:6px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}}
.kpi{{background:#fff;border:1px solid var(--b);border-radius:12px;padding:14px}}.kpi b{{display:block;font-size:28px;color:var(--p)}}
.nota{{background:#fff7e6;border-left:4px solid #d97706;padding:12px 16px;border-radius:8px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden}}th,td{{padding:8px 10px;border-bottom:1px solid var(--b);text-align:left;font-size:14px}}th{{background:#efeafa}}
.h{{background:#fff;border:1px solid var(--b);border-radius:14px;padding:18px;margin:18px 0}}
.h header{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}.h h3{{margin:0;flex:1 1 300px;font-size:18px}}
.id{{font-weight:700;color:var(--p)}}.tag{{font-size:12px;font-weight:600;padding:3px 10px;border-radius:99px;background:#eee}}
.ok{{background:#dcfce7;color:#166534}}.pend{{background:#fef3c7;color:#92400e}}.org{{background:#ede9fe;color:#5b21b6}}
.sev-alta{{background:#fee2e2;color:#991b1b}}.sev-media{{background:#ffedd5;color:#9a3412}}.sev-baja{{background:#e0f2fe;color:#075985}}
dl{{display:grid;grid-template-columns:200px 1fr;gap:6px 14px;margin:14px 0}}dt{{font-weight:600;color:var(--m)}}dd{{margin:0}}
.imgs{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}figure{{margin:0}}figcaption{{font-weight:600;font-size:13px;color:var(--m)}}
img{{width:100%;max-height:420px;object-fit:cover;object-position:top;border:1px solid var(--b);border-radius:8px}}
.sin{{display:flex;align-items:center;justify-content:center;min-height:120px;border:2px dashed var(--b);border-radius:8px;color:var(--m);font-size:13px}}
@media(max-width:700px){{dl{{grid-template-columns:1fr}}.imgs{{grid-template-columns:1fr}}}}
a{{color:var(--p)}}
</style></head><body><main>
<h1>Registro de pruebas de usabilidad — LBWUS</h1>
<p>Tarea 10.2 · {date.today():%d-%m-%Y} · Escritorio (1366×800) y móvil (390×844)</p>

<div class="kpis">
<div class="kpi"><b>24</b>flujos recorridos</div><div class="kpi"><b>48</b>pantallas capturadas</div>
<div class="kpi"><b>{total}</b>hallazgos</div><div class="kpi"><b>{corr}</b>corregidos</div>
<div class="kpi"><b>{altas_ok}/{altas}</b>severidad alta resueltos</div></div>

<p class="nota"><b>Alcance:</b> esta ronda es un <b>recorrido guiado</b> (evaluación experta + navegador automatizado
con Edge en escritorio y móvil). Detecta errores objetivos y problemas de comprensión evidentes, pero
<b>no reemplaza la prueba con usuarios reales</b>. Las observaciones de participantes se agregan como
hallazgos con origen «Usuario» (ver «Cómo continuar»).</p>

<h2>Resumen ejecutivo</h2>
<ul>
<li><b>Lo más grave ya está corregido:</b> el buscador de profesionales no filtraba al pegar o autocompletar, el panel del alumno mostraba datos inventados y el simulador escondía el menú del sitio.</li>
<li><b>Patrón principal pendiente:</b> varias pantallas muestran <b>datos de ejemplo como si fueran reales</b> (distancias, notas, tutores, gráficos). Es lo que más confunde y lo que más baja la credibilidad.</li>
<li><b>Falta un flujo completo:</b> no existe perfil del profesional ni reserva con un profesor específico; hoy se reserva desde un catálogo general.</li>
</ul>

<h2>Índice de hallazgos</h2>
<table><thead><tr><th>ID</th><th>Flujo</th><th>Severidad</th><th>Estado</th></tr></thead><tbody>{filas}</tbody></table>

<h2>Hallazgos con evidencia</h2>
{''.join(tarjeta(h) for h in HALLAZGOS)}

<h2>Qué funcionó bien</h2><ul>{fort}</ul>

<h2>Flujos recorridos</h2>
<table><thead><tr><th>#</th><th>Flujo</th><th>Rol</th><th>Vistas</th></tr></thead><tbody>{tabla_flujos()}</tbody></table>

<h2>Cómo continuar con usuarios reales</h2>
<ol>
<li>Levantar la demo: <code>usabilidad\\levantar_demo.bat</code> → <code>http://127.0.0.1:8765</code> (usa una base aparte).</li>
<li>Pedir a 3–5 personas que completen sin ayuda: registrarse, iniciar sesión, buscar un profesor de Matemáticas, inscribirse a su clase y volver a «Mi espacio». Anotar dónde dudan.</li>
<li>Agregar cada observación en <code>HALLAZGOS</code> dentro de <code>usabilidad/generar_registro.py</code> con <code>origen='Usuario'</code> y ejecutar <code>python usabilidad/generar_registro.py</code>.</li>
<li>Repetir el recorrido automático tras cada corrección: <code>python usabilidad/recorrido.py --etiqueta despues</code>.</li>
</ol>

<h2>Conclusiones</h2>
<p>Los flujos de registro, inicio de sesión y navegación por rol se completan sin ayuda. La mayor barrera para un usuario
nuevo no es la navegación, sino la <b>confianza en lo que ve</b>: números y personas que no existen. Se recomienda priorizar
H07 (perfil del profesional) y H08–H10 (quitar datos de ejemplo) antes de la presentación final.</p>
</main></body></html>'''
    destino = AQUI / 'REGISTRO_USABILIDAD.html'
    destino.write_text(pagina, encoding='utf-8')
    print(destino)


if __name__ == '__main__':
    generar()
