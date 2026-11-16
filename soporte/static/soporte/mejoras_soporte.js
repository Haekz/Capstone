/* Portal de soporte: mejoras de uso (de la copia: bloque 4). Plazo en palabras bajo cada vencimiento, banner de Mis tickets con
   las cifras del dia, fila entera como enlace, filtro de la tabla, contador y validacion de las respuestas, confirmacion
   antes de escalar y buscador Ctrl+K con las secciones del menu y los tickets de la pagina. Solo usa lo que el servidor ya
   pinto; cada parte revisa que su elemento exista. Va al final de base_soporte.html (usa openSearchModal y closeSearchModal
   de base_admin.html). */
/* Solo usa lo que el servidor ya pintó en la página: no hay llamadas nuevas.
   Cada parte revisa que su elemento exista, así sirve en cualquier pantalla del portal. */
(() => {
    'use strict';
    const $ = (sel, raiz = document) => raiz.querySelector(sel);
    const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];
    const esc = window.escaparHtml || (s => String(s));
    const normalizar = s => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

    /* ── Fechas y plazos ── */
    const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
    const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
        'septiembre', 'octubre', 'noviembre', 'diciembre'];
    const inicioDia = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const hora = d => String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');

    // Lee <time datetime="…">; si no trae el atributo, entiende "dd-mm-aaaa hh:mm"
    function leerFecha(el) {
        if (!el) return null;
        const iso = el.getAttribute('datetime');
        if (iso) {
            const d = new Date(iso);
            if (!isNaN(d)) return d;
        }
        const m = el.textContent.match(/(\d{1,2})-(\d{1,2})-(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/);
        return m ? new Date(+m[3], m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0)) : null;
    }

    function plazo(vence) {
        const ahora = new Date();
        const dias = Math.round((inicioDia(vence) - inicioDia(ahora)) / 864e5);
        if (vence < ahora) return { texto: 'Vencido', tono: 'vencido', dias };
        if (dias === 0) return { texto: 'Vence hoy, ' + hora(vence), tono: 'pronto', dias };
        if (dias === 1) return { texto: 'Vence mañana, ' + hora(vence), tono: 'pronto', dias };
        if (dias < 7) return { texto: 'Vence el ' + DIAS[vence.getDay()] + ', ' + hora(vence), tono: 'normal', dias };
        return { texto: 'Vence en ' + dias + ' días', tono: 'normal', dias };
    }

    // Bajo cada fecha de vencimiento, una ficha con el plazo en palabras
    $$('time.sop-vence').forEach(t => {
        const d = leerFecha(t);
        if (!d) return;
        const p = plazo(d);
        const ficha = document.createElement('span');
        ficha.className = 'sop-plazo sop-plazo--' + p.tono;
        ficha.textContent = p.texto;
        t.after(ficha);
    });

    /* ── Mis tickets: banner, fila entera como enlace, filtro ── */
    const tabla = $('.sop-tabla-tickets');
    const filas = tabla ? $$('tbody tr', tabla).filter(tr => !tr.querySelector('td[colspan]')) : [];

    const hoy = $('#sop-hoy');
    if (hoy) {
        const d = new Date();
        const texto = DIAS[d.getDay()] + ' ' + d.getDate() + ' de ' + MESES[d.getMonth()];
        hoy.textContent = texto.charAt(0).toUpperCase() + texto.slice(1);
    }

    if (tabla && $('#sop-resumen')) {
        const datos = filas.map(tr => {
            const vence = leerFecha($('time.sop-vence', tr));
            return { tr, vence, p: vence ? plazo(vence) : null, enlace: $('a.sop-ticket', tr) };
        });
        const pronto = datos.filter(x => x.p && x.p.tono === 'pronto').length;
        const vencidos = datos.filter(x => x.p && x.p.tono === 'vencido').length;
        const n = datos.length;

        $('#sop-n-abiertos').textContent = n;
        $('#sop-n-pronto').textContent = pronto;
        $('#sop-n-vencidos').textContent = vencidos;
        $('#sop-c-pronto').classList.toggle('sop-cifra--hay', pronto > 0);
        $('#sop-c-vencidos').classList.toggle('sop-cifra--alerta', vencidos > 0);
        $('#sop-cifras').hidden = false;

        // El siguiente paso: el ticket que vence antes (los vencidos primero)
        const siguiente = datos.filter(x => x.vence && x.enlace).sort((a, b) => a.vence - b.vence)[0];
        let resumen;
        if (!n) {
            resumen = 'No tienes tickets abiertos.';
        } else {
            resumen = n === 1 ? 'Tienes 1 ticket abierto' : `Tienes ${n} tickets abiertos`;
            if (vencidos) resumen += vencidos === 1 ? (n === 1 ? ' y ya venció' : ' y 1 ya venció') : ` y ${vencidos} ya vencieron`;
            resumen += '.';
            if (siguiente) {
                const num = $('.sop-ticket-num', siguiente.enlace)?.textContent.trim() || '';
                const cuando = siguiente.p.texto.charAt(0).toLowerCase() + siguiente.p.texto.slice(1);
                if (siguiente.p.tono === 'vencido') resumen += ` Empieza por el ${num}.`;
                else if (n === 1) resumen = `Tienes 1 ticket abierto: el ${num}, que ${cuando}.`;
                else resumen += ` El más urgente es el ${num}: ${cuando}.`;
                const btn = $('#sop-siguiente');
                btn.href = siguiente.enlace.getAttribute('href');
                $('span', btn).textContent = 'Revisar el ticket ' + num;
                btn.hidden = false;
            }
        }
        $('#sop-resumen').textContent = resumen;
    }

    // La fila entera abre el ticket (los botones de la fila siguen funcionando igual)
    filas.forEach(tr => {
        const enlace = $('a.sop-ticket', tr);
        if (!enlace) return;
        tr.addEventListener('click', ev => {
            if (ev.target.closest('a, button, input, label')) return;
            if (window.getSelection && String(window.getSelection())) return;  // estaba copiando texto
            enlace.click();
        });
    });

    // Con más de 5 tickets aparece el buscador de la tabla
    const filtro = $('#sop-filtro');
    if (filtro && filas.length > 5) {
        filtro.closest('.sop-filtro').hidden = false;
        const sinRes = $('#sop-sin-resultados');
        filtro.addEventListener('input', () => {
            const q = normalizar(filtro.value);
            let visibles = 0;
            filas.forEach(tr => {
                const ok = !q || normalizar(tr.textContent).includes(q);
                tr.hidden = !ok;
                if (ok) visibles++;
            });
            if (sinRes) sinRes.hidden = visibles > 0;
        });
    }

    /* ── Formularios: contador, alto automático, validación, doble envío ── */
    const MENSAJES = {
        id_texto: 'Escribe la respuesta antes de enviarla.',
        id_motivo: 'Cuenta por qué escalas este ticket.'
    };

    function limpiarError(campo) {
        campo.removeAttribute('aria-invalid');
        const err = document.getElementById(campo.id + '-error');
        if (err) err.remove();
        const desc = (campo.getAttribute('aria-describedby') || '').split(' ').filter(x => x && x !== campo.id + '-error');
        if (desc.length) campo.setAttribute('aria-describedby', desc.join(' '));
    }

    function marcarError(campo) {
        limpiarError(campo);
        const err = document.createElement('p');
        err.className = 'sop-error';
        err.id = campo.id + '-error';
        err.innerHTML = '<i class="bi bi-exclamation-circle-fill" aria-hidden="true"></i> ' + esc(MENSAJES[campo.id] || 'Completa este campo.');
        const pie = campo.parentElement.querySelector('.sop-campo-pie') || campo;
        pie.after(err);
        campo.setAttribute('aria-invalid', 'true');
        campo.setAttribute('aria-describedby', ((campo.getAttribute('aria-describedby') || '') + ' ' + err.id).trim());
    }

    $$('form.apod-form').forEach(form => {
        const boton = $('button[type="submit"]', form);
        const textos = $$('textarea', form);

        textos.forEach(campo => {
            const max = parseInt(campo.getAttribute('maxlength'), 10);
            const ayuda = campo.parentElement.querySelector('small');
            if (max) {
                const pie = document.createElement('div');
                pie.className = 'sop-campo-pie';
                const contador = document.createElement('span');
                contador.className = 'sop-contador';
                contador.setAttribute('aria-hidden', 'true');
                if (ayuda) { ayuda.before(pie); pie.append(ayuda); } else { campo.after(pie); }
                pie.append(contador);
                const contar = () => {
                    const n = campo.value.length;
                    contador.textContent = n + ' / ' + max;
                    contador.classList.toggle('sop-contador--cerca', n >= max * 0.9);
                };
                campo.addEventListener('input', contar);
                contar();
            }
            const crecer = () => {
                campo.style.height = 'auto';
                campo.style.height = Math.min(campo.scrollHeight + 2, 420) + 'px';
            };
            campo.addEventListener('input', () => { crecer(); if (campo.value.trim()) limpiarError(campo); });
            // Ctrl + Enter envía (pasando por la misma validación)
            campo.addEventListener('keydown', ev => {
                if ((ev.ctrlKey || ev.metaKey) && ev.key === 'Enter') {
                    ev.preventDefault();
                    form.requestSubmit ? form.requestSubmit(boton) : boton.click();
                }
            });
        });

        // "Cerrar el ticket con esta respuesta": el botón dice lo que va a pasar
        const cerrar = $('input[name="cerrar"]', form);
        let textoBoton = boton ? boton.innerHTML : '';
        if (cerrar && boton) {
            const original = boton.innerHTML;
            const actualizar = () => {
                boton.innerHTML = cerrar.checked
                    ? '<i class="bi bi-check2-circle" aria-hidden="true"></i> Enviar y cerrar ticket'
                    : original;
                textoBoton = boton.innerHTML;
            };
            cerrar.addEventListener('change', actualizar);
            actualizar();
        }

        const escalar = textos.some(t => t.name === 'motivo');
        let confirmado = false;

        form.addEventListener('submit', ev => {
            const vacios = textos.filter(t => t.required && !t.value.trim());
            textos.forEach(limpiarError);
            if (vacios.length) {
                ev.preventDefault();
                vacios.forEach(marcarError);
                vacios[0].focus();
                return;
            }
            if (boton && boton.disabled) { ev.preventDefault(); return; }

            // Escalar saca el ticket del panel: se confirma antes
            if (escalar && !confirmado) {
                ev.preventDefault();
                const num = (($('#section-title') || {}).textContent || '').match(/#\d+/);
                const titulo = '¿Escalar el ticket' + (num ? ' ' + num[0] : '') + '?';
                const texto = 'Pasará al líder de soporte y dejará de aparecer en tu panel. El plazo no cambia.';
                const seguir = () => { confirmado = true; form.requestSubmit ? form.requestSubmit(boton) : form.submit(); };
                if (window.Swal) {
                    Swal.fire({
                        title: titulo,
                        text: texto,
                        showCancelButton: true,
                        confirmButtonText: 'Escalar',
                        cancelButtonText: 'Cancelar',
                        focusCancel: true
                    }).then(r => { if (r.isConfirmed) seguir(); });
                } else if (window.confirm(titulo + '\n\n' + texto)) {
                    seguir();
                }
                return;
            }

            if (boton) {
                boton.disabled = true;
                boton.innerHTML = '<i class="bi bi-hourglass-split" aria-hidden="true"></i> ' + (escalar ? 'Escalando…' : 'Enviando…');
            }
        });

        // Si el navegador vuelve a la página desde su memoria, el botón vuelve a estar listo
        window.addEventListener('pageshow', () => {
            if (boton) { boton.disabled = false; boton.innerHTML = textoBoton; }
            confirmado = false;
        });
    });

    /* ── Buscador (Ctrl + K): secciones del menú y tickets de esta página ── */
    function destinos() {
        const secciones = $$('.sidebar-nav a.nav-item').map(a => ({
            titulo: a.textContent.trim(),
            href: a.getAttribute('href'),
            icono: ((a.querySelector('i') || {}).className || '').match(/bi-[\w-]+/)?.[0] || 'bi-arrow-right',
            tipo: 'Sección'
        }));
        const tickets = filas.map(tr => {
            const a = $('a.sop-ticket', tr);
            return a && {
                num: $('.sop-ticket-num', a)?.textContent.trim() || '',
                titulo: $('.sop-ticket-asunto', a)?.textContent.trim() || a.textContent.trim(),
                extra: tr.textContent,
                href: a.getAttribute('href'),
                icono: 'bi-chat-left-text',
                tipo: 'Ticket'
            };
        }).filter(Boolean);
        return { secciones, tickets };
    }

    const item = d => `
        <a class="search-result-item" href="${esc(d.href)}">
            <i class="bi ${esc(d.icono)}" aria-hidden="true"></i>
            <span>${d.num ? `<span class="sop-buscar-num">${esc(d.num)}</span> ` : ''}${esc(d.titulo)}</span>
            <span class="search-result-type">${esc(d.tipo)}</span>
        </a>`;

    window.handleGlobalSearch = function () {
        const input = $('#search-modal-input');
        const caja = $('#search-modal-results');
        if (!input || !caja) return;
        const q = normalizar(input.value);
        const { secciones, tickets } = destinos();
        const coincide = d => !q || normalizar(d.titulo + ' ' + (d.num || '') + ' ' + (d.extra || '')).includes(q);
        const s = secciones.filter(coincide);
        const t = tickets.filter(coincide);
        let html = '';
        if (s.length) html += '<div class="search-section-label">Secciones</div>' + s.map(item).join('');
        if (t.length) html += '<div class="search-section-label">Tickets</div>' + t.map(item).join('');
        caja.innerHTML = html || `<p class="search-sin-resultados">No hay secciones ni tickets que coincidan con «${esc(input.value.trim())}».</p>`;
        const primero = $('.search-result-item', caja);
        if (primero && q) primero.classList.add('sop-elegido');
    };

    window.navigateFromSearch = function (destino) {
        window.closeSearchModal();
        location.hash = destino;
    };

    const abrirBuscador = window.openSearchModal;
    if (abrirBuscador) {
        window.openSearchModal = function () {
            abrirBuscador();
            window.handleGlobalSearch();
        };
    }

    const caja = $('#search-modal-results');
    if (caja) caja.addEventListener('click', ev => { if (ev.target.closest('a')) window.closeSearchModal(); });

    const entrada = $('#search-modal-input');
    if (entrada) {
        entrada.addEventListener('keydown', ev => {
            if (ev.key === 'Enter') {
                const primero = $('#search-modal-results .search-result-item');
                if (primero) { ev.preventDefault(); primero.click(); }
            } else if (ev.key === 'ArrowDown') {
                const primero = $('#search-modal-results .search-result-item');
                if (primero) { ev.preventDefault(); primero.focus(); }
            }
        });
    }

    // Flechas dentro de la lista de resultados
    if (caja) caja.addEventListener('keydown', ev => {
        if (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp') return;
        const items = $$('.search-result-item', caja);
        const i = items.indexOf(document.activeElement);
        if (i < 0) return;
        ev.preventDefault();
        if (ev.key === 'ArrowUp' && i === 0) { entrada && entrada.focus(); return; }
        (items[i + (ev.key === 'ArrowDown' ? 1 : -1)] || items[i]).focus();
    });

    // Esc también cierra las notificaciones
    window.addEventListener('keydown', ev => {
        if (ev.key === 'Escape') $('#notifications-drawer')?.classList.remove('active');
    });

    /* ── Título de la pestaña y enlace activo para lectores de pantalla ── */
    function sincronizar() {
        const h1 = $('#section-title');
        if (h1) document.title = h1.textContent.trim() + ' — Soporte LBWUS';
        $$('.sidebar-nav a.nav-item').forEach(a => {
            if (a.classList.contains('active')) a.setAttribute('aria-current', 'page');
            else a.removeAttribute('aria-current');
        });
    }
    window.addEventListener('hashchange', sincronizar);
    sincronizar();
})();
