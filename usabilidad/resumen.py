import json
import sys

datos = json.load(open(sys.argv[1], encoding='utf-8'))
for r in datos:
    p = []
    if r.get('fallo'):
        p.append('FALLO: ' + r['fallo'][:150])
    if r.get('scrollHorizontal'):
        p.append(f"SCROLL-H {r['anchoDoc']}>{r['anchoVista']} {r['desbordan'][:3]}")
    for k in ('errores_consola', 'recursos_fallidos', 'sinEtiqueta', 'sinNombre', 'enlacesVacios', 'objetivosChicos'):
        if r.get(k):
            p.append(f"{k}: {r[k][:4]}")
    if r.get('mensajes'):
        p.append('MSG: ' + ' | '.join(r['mensajes'])[:200])
    print(f"[{r['id']} {r['vista'][:3]}] {r['flujo']} -> {r.get('url','')} | {r.get('titulo','')}")
    for x in p:
        print('    ' + x)
