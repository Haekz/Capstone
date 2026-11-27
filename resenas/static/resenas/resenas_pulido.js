/* Reseñas: color de avatar, fecha relativa, "X de Y le dan 4 o 5 estrellas", filtro por estrellas, orden y páginas.
   Viene de la copia de reseñas. Solo usa lo que el servidor ya pintó (sin llamadas nuevas) y cada parte revisa que su
   elemento exista, así sirve en el perfil del profesor y en Mis reseñas. Sin JavaScript se ve la lista completa. */
(() => {
    'use strict';
    const $ = (sel, raiz = document) => raiz.querySelector(sel);
    const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];
    const sinMovimiento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ── Reseñas: color de avatar, fecha relativa y "X de Y le dan 4 o 5 estrellas" ── */
    const TONOS = [270, 330, 200, 160, 30, 230];  // morado, rosa, celeste, verde, ámbar, azul
    const hace = iso => {
        const [y, m, d] = (iso || '').split('-').map(Number);
        if (!y) return '';
        const hoy = new Date();
        const dias = Math.round((new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate()) - new Date(y, m - 1, d)) / 864e5);
        if (dias < 0) return '';
        if (dias === 0) return 'hoy';
        if (dias === 1) return 'ayer';
        if (dias < 7) return `hace ${dias} días`;
        if (dias < 30) { const s = Math.floor(dias / 7); return s === 1 ? 'hace 1 semana' : `hace ${s} semanas`; }
        return '';
    };
    $$('.resena').forEach(li => {
        const nombre = ($('.resena__autor strong', li) || {}).textContent || '';
        let h = 0;
        for (const c of nombre) h = (h * 31 + c.charCodeAt(0)) >>> 0;
        const av = $('.resena__avatar', li);
        if (av) av.style.setProperty('--av-h', TONOS[h % TONOS.length]);
        const t = $('time.resena__fecha', li);
        const rel = t && hace(t.getAttribute('datetime'));
        if (rel) { t.title = t.textContent.trim(); t.textContent = rel; }
    });
    $$('.resena-resumen').forEach(r => {
        const cant = n => {
            const li = $$('.resena-resumen__barras li', r).find(x => parseInt(($('.resena-resumen__etiqueta', x) || {}).textContent, 10) === n);
            return li ? parseInt(($('.resena-resumen__cantidad', li) || {}).textContent, 10) || 0 : 0;
        };
        const total = [1, 2, 3, 4, 5].reduce((a, n) => a + cant(n), 0);
        const nota = $('.resena-resumen__nota', r);
        if (!total || !nota) return;
        const p = document.createElement('p');
        p.className = 'resena-resumen__extra';
        p.textContent = `${cant(4) + cant(5)} de ${total} le dan 4 o 5 estrellas`;
        nota.append(p);
    });

    /* ── Reseñas: filtro por estrellas, orden y páginas ── */
    $$('.resenas').forEach(seccion => {
        const lista = $('.resena-lista', seccion);
        const items = lista ? $$(':scope > li.resena', lista) : [];
        if (!items.length) return;

        const POR_PAGINA = 5;
        const puntaje = li => Number(li.dataset.puntaje) ||
            Number(((($('.resena-estrellas', li) || {}).getAttribute?.('aria-label') || '').match(/(\d) de 5/) || [])[1]) || 0;
        const fecha = li => ($('time', li) || {}).getAttribute?.('datetime') || '';
        items.forEach((li, i) => { li.dataset.posicion = i; });

        const barra = $('.resenas-barra', seccion);
        const estado = $('.resenas-barra__estado', seccion);
        const orden = $('.resenas-barra__orden select', seccion);
        const paginas = $('.resenas-paginas', seccion);
        let filtro = 0;
        let pagina = 1;

        // Las barras del resumen filtran al apretarlas (las de 0 reseñas no)
        const barras = $$('.resena-resumen__barras li', seccion).map(li => {
            const n = parseInt(($('.resena-resumen__etiqueta', li) || {}).textContent, 10);
            const cant = parseInt(($('.resena-resumen__cantidad', li) || {}).textContent, 10) || 0;
            if (!n) return null;
            if (!cant) { li.classList.add('resena-resumen__barra--vacia'); return null; }
            li.tabIndex = 0;
            li.setAttribute('role', 'button');
            li.setAttribute('aria-pressed', 'false');
            li.setAttribute('aria-label', `Ver solo las reseñas de ${n} ${n === 1 ? 'estrella' : 'estrellas'} (${cant})`);
            const elegir = () => { filtro = filtro === n ? 0 : n; pagina = 1; pintar(); };
            li.addEventListener('click', elegir);
            li.addEventListener('keydown', ev => {
                if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); elegir(); }
            });
            return { li, n };
        }).filter(Boolean);

        const comparar = {
            recientes: (a, b) => fecha(b).localeCompare(fecha(a)) || a.dataset.posicion - b.dataset.posicion,
            mejores: (a, b) => puntaje(b) - puntaje(a) || fecha(b).localeCompare(fecha(a)),
            peores: (a, b) => puntaje(a) - puntaje(b) || fecha(b).localeCompare(fecha(a))
        };

        function pintar(llevar) {
            const visibles = items.filter(li => !filtro || puntaje(li) === filtro)
                .sort(comparar[orden ? orden.value : 'recientes']);
            [...visibles, ...items.filter(li => !visibles.includes(li))].forEach(li => lista.append(li));

            const total = Math.max(1, Math.ceil(visibles.length / POR_PAGINA));
            pagina = Math.min(Math.max(1, pagina), total);
            const desde = (pagina - 1) * POR_PAGINA;
            const enPagina = visibles.slice(desde, desde + POR_PAGINA);
            items.forEach(li => { li.hidden = !enPagina.includes(li); li.classList.remove('resena--primera'); });
            if (enPagina[0]) enPagina[0].classList.add('resena--primera');

            barras.forEach(b => b.li.setAttribute('aria-pressed', String(b.n === filtro)));

            if (estado) {
                const rango = visibles.length > POR_PAGINA
                    ? `Mostrando <strong>${desde + 1}–${desde + enPagina.length}</strong> de ${visibles.length}`
                    : `<strong>${visibles.length}</strong> ${visibles.length === 1 ? 'reseña' : 'reseñas'}`;
                estado.innerHTML = filtro
                    ? `${rango} con ${filtro} ${filtro === 1 ? 'estrella' : 'estrellas'} <button type="button" class="resenas-barra__quitar"><i class="bi bi-x" aria-hidden="true"></i> Ver todas</button>`
                    : rango;
            }

            if (paginas) {
                paginas.hidden = total < 2;
                let html = `<button type="button" data-pagina="${pagina - 1}" ${pagina === 1 ? 'disabled' : ''} aria-label="Página anterior"><i class="bi bi-arrow-left" aria-hidden="true"></i></button>`;
                for (let i = 1; i <= total; i++) {
                    html += `<button type="button" data-pagina="${i}" ${i === pagina ? 'aria-current="page"' : ''} aria-label="Página ${i}">${i}</button>`;
                }
                html += `<button type="button" data-pagina="${pagina + 1}" ${pagina === total ? 'disabled' : ''}>Siguiente <i class="bi bi-arrow-right" aria-hidden="true"></i></button>`;
                paginas.innerHTML = html;
            }
            if (llevar) (barra || lista).scrollIntoView({ block: 'start', behavior: sinMovimiento ? 'auto' : 'smooth' });
        }

        if (barra) barra.hidden = false;
        if (orden) orden.addEventListener('change', () => { pagina = 1; pintar(); });
        if (estado) estado.addEventListener('click', ev => {
            if (ev.target.closest('.resenas-barra__quitar')) { filtro = 0; pagina = 1; pintar(); }
        });
        if (paginas) paginas.addEventListener('click', ev => {
            const b = ev.target.closest('button[data-pagina]');
            if (!b || b.disabled) return;
            pagina = Number(b.dataset.pagina);
            pintar(true);
        });
        pintar();
    });
})();
