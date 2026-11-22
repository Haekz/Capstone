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
    const esc = window.escaparHtml;
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

    /* ── Tickets: banner, fila entera como enlace, filtros ── */
    // Agente: una tabla (sus tickets). Líder: la suya (--mios) y la del equipo (--equipo).
    const filasDe = t => t ? $$('tbody tr', t).filter(tr => !tr.querySelector('td[colspan]')) : [];
    const tablas = $$('.sop-tabla-tickets');
    const tablaMia = $('.sop-tabla-tickets--mios') || tablas[0] || null;
    const tablaCifras = $('.sop-tabla-tickets--equipo') || tablaMia;
    const filas = tablas.flatMap(filasDe);
    const datosDe = t => filasDe(t).map(tr => {
        const vence = leerFecha($('time.sop-vence', tr));
        return { tr, vence, p: vence ? plazo(vence) : null, enlace: $('a.sop-ticket', tr) };
    });

    const hoy = $('#sop-hoy');
    if (hoy) {
        const d = new Date();
        const texto = DIAS[d.getDay()] + ' ' + d.getDate() + ' de ' + MESES[d.getMonth()];
        hoy.textContent = texto.charAt(0).toUpperCase() + texto.slice(1);
    }

    if (tablaMia && $('#sop-resumen')) {
        // Cifras: las del equipo si la tabla está en la página; si no, las propias
        const todos = datosDe(tablaCifras);
        const pronto = todos.filter(x => x.p && x.p.tono === 'pronto').length;
        const vencidos = todos.filter(x => x.p && x.p.tono === 'vencido').length;
        $('#sop-n-abiertos').textContent = todos.length;
        $('#sop-n-pronto').textContent = pronto;
        $('#sop-n-vencidos').textContent = vencidos;
        $('#sop-c-pronto').classList.toggle('sop-cifra--hay', pronto > 0);
        $('#sop-c-vencidos').classList.toggle('sop-cifra--alerta', vencidos > 0);
        $('#sop-cifras').hidden = false;

        // Resumen y siguiente paso: siempre con los tickets propios (los vencidos primero)
        const mios = datosDe(tablaMia);
        const n = mios.length;
        const misVencidos = mios.filter(x => x.p && x.p.tono === 'vencido').length;
        const siguiente = mios.filter(x => x.vence && x.enlace).sort((a, b) => a.vence - b.vence)[0];
        let resumen;
        if (!n) {
            resumen = 'No tienes tickets abiertos.';
        } else {
            resumen = n === 1 ? 'Tienes 1 ticket abierto' : `Tienes ${n} tickets abiertos`;
            if (misVencidos) resumen += misVencidos === 1 ? (n === 1 ? ' y ya venció' : ' y 1 ya venció') : ` y ${misVencidos} ya vencieron`;
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

    // La fila entera abre el ticket (los botones y el formulario de la fila siguen funcionando igual)
    filas.forEach(tr => {
        const enlace = $('a.sop-ticket', tr);
        if (!enlace) return;
        tr.addEventListener('click', ev => {
            if (ev.target.closest('a, button, input, label, select, form')) return;
            if (window.getSelection && String(window.getSelection())) return;  // estaba copiando texto
            enlace.click();
        });
    });

    // Por tabla: buscador (con más de 5 tickets) y botones por agente (si hay más de uno)
    tablas.forEach(t => {
        const panel = t.closest('.panel') || t.parentElement;
        const propias = filasDe(t);
        const entrada = $('.sop-filtro input', panel);
        const sinRes = $('.sop-sin-resultados', panel);
        const caja = $('.sop-filtro-agentes', panel);
        let texto = '';
        let agente = '';
        const agenteDe = tr => ($('.sop-persona-nombre', tr) || $('.sop-asignado', tr))?.textContent.trim() || '';
        const aplicar = () => {
            let visibles = 0;
            propias.forEach(tr => {
                const ok = (!texto || normalizar(tr.textContent).includes(texto)) && (!agente || agenteDe(tr) === agente);
                tr.hidden = !ok;
                if (ok) visibles++;
            });
            if (sinRes) sinRes.hidden = visibles > 0;
        };
        if (entrada && propias.length > 5) {
            entrada.closest('.sop-filtro').hidden = false;
            entrada.addEventListener('input', () => { texto = normalizar(entrada.value); aplicar(); });
        }
        if (caja) {
            const cuenta = {};
            propias.forEach(tr => { const a = agenteDe(tr); if (a) cuenta[a] = (cuenta[a] || 0) + 1; });
            const nombres = Object.keys(cuenta).sort((a, b) => a.localeCompare(b, 'es'));
            if (nombres.length > 1) {
                const boton = (valor, etiqueta, n) =>
                    `<button type="button" class="sop-chip-filtro" data-agente="${esc(valor)}" aria-pressed="${valor === '' ? 'true' : 'false'}">${esc(etiqueta)} <span>${n}</span></button>`;
                caja.innerHTML = boton('', 'Todos', propias.length) + nombres.map(a => boton(a, a, cuenta[a])).join('');
                caja.hidden = false;
                caja.addEventListener('click', ev => {
                    const b = ev.target.closest('.sop-chip-filtro');
                    if (!b) return;
                    agente = b.dataset.agente;
                    $$('.sop-chip-filtro', caja).forEach(x => x.setAttribute('aria-pressed', String(x === b)));
                    aplicar();
                });
            }
        }
    });

    /* ── Reasignar: el botón se activa solo si eliges a otro agente ── */
    $$('form.sop-reasignar').forEach(form => {
        const sel = $('select', form);
        const btn = $('button[type="submit"]', form);
        if (!sel || !btn) return;
        const actual = sel.value;
        const original = btn.innerHTML;
        const revisar = () => {
            btn.disabled = sel.value === actual;
            btn.title = btn.disabled ? 'Elige otro agente para reasignar' : '';
            btn.classList.toggle('sop-btn--primario', !btn.disabled);
        };
        sel.addEventListener('change', revisar);
        revisar();
        form.addEventListener('submit', ev => {
            if (sel.value === actual || form.dataset.enviando) { ev.preventDefault(); return; }
            form.dataset.enviando = '1';
            btn.disabled = true;
            btn.innerHTML = '<i class="bi bi-hourglass-split" aria-hidden="true"></i> Reasignando…';
        });
        window.addEventListener('pageshow', () => { delete form.dataset.enviando; btn.innerHTML = original; revisar(); });
    });

    /* ── Equipo: categorías resumidas y barra de carga ── */
    const agentes = $$('.sop-agente');
    const maxCarga = Math.max(1, ...agentes.map(a => parseInt($('.sop-carga-n', a)?.textContent, 10) || 0));
    agentes.forEach(a => {
        const n = parseInt($('.sop-carga-n', a)?.textContent, 10) || 0;
        const barra = $('.sop-carga-barra > span', a);
        if (barra) barra.style.width = Math.round(n / maxCarga * 100) + '%';
        const cats = $('.sop-agente-cats', a);
        const chips = cats ? $$('.badge', cats) : [];
        const VISIBLES = 4;
        if (chips.length > VISIBLES + 1) {
            const extra = chips.slice(VISIBLES);
            extra.forEach(c => { c.hidden = true; });
            const mas = document.createElement('button');
            mas.type = 'button';
            mas.className = 'sop-cats-mas';
            mas.setAttribute('aria-expanded', 'false');
            const etiqueta = () => mas.getAttribute('aria-expanded') === 'true' ? 'Ver menos' : `+${extra.length} más`;
            mas.textContent = etiqueta();
            mas.addEventListener('click', () => {
                const abrir = mas.getAttribute('aria-expanded') !== 'true';
                extra.forEach(c => { c.hidden = !abrir; });
                mas.setAttribute('aria-expanded', String(abrir));
                mas.textContent = etiqueta();
            });
            cats.append(mas);
        }
    });

    /* ── Registros plegables: cuántas filas trae cada uno ── */
    $$('details.sop-registro').forEach(d => {
        const n = $$('tbody tr', d).filter(tr => !tr.querySelector('td[colspan]')).length;
        const titulo = $('summary .panel-title', d);
        if (!titulo) return;
        const c = document.createElement('span');
        c.className = 'sop-cuenta' + (n ? '' : ' sop-cuenta--cero');
        c.textContent = n;
        titulo.append(c);
    });

    /* ── Formularios: contador, alto automático, validación, doble envío ── */
    const MENSAJES = {
        texto: 'Escribe la respuesta antes de enviarla.',
        motivo: 'Cuenta por qué escalas este ticket.',
        autoridad: 'Escribe qué autoridad lo pide.',
        referencia: 'Escribe el número de oficio, causa o RIT.',
        recibido: 'Indica cuándo llegó el requerimiento.',
        alcance: 'Describe qué datos pide.'
    };
    const hoyISO = (() => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); })();

    // Devuelve el problema del campo, o nada si está bien
    function revisarCampo(campo, form) {
        const v = campo.value.trim();
        if (campo.required && !v) return MENSAJES[campo.name] || 'Completa este campo.';
        if (campo.type === 'date' && v) {
            if (campo.name === 'recibido' && v > hoyISO) return 'La fecha no puede ser posterior a hoy.';
            const recibido = $('input[name="recibido"]', form);
            if (campo.name === 'vence' && recibido && recibido.value && v < recibido.value)
                return 'El plazo no puede ser anterior a la fecha en que llegó.';
        }
        return '';
    }

    function limpiarError(campo) {
        campo.removeAttribute('aria-invalid');
        const err = document.getElementById(campo.id + '-error');
        if (err) err.remove();
        const desc = (campo.getAttribute('aria-describedby') || '').split(' ').filter(x => x && x !== campo.id + '-error');
        if (desc.length) campo.setAttribute('aria-describedby', desc.join(' '));
        else campo.removeAttribute('aria-describedby');
    }

    function marcarError(campo, mensaje) {
        limpiarError(campo);
        const err = document.createElement('p');
        err.className = 'sop-error';
        err.id = campo.id + '-error';
        err.innerHTML = '<i class="bi bi-exclamation-circle-fill" aria-hidden="true"></i> ' + esc(mensaje);
        const pie = campo.parentElement.querySelector('.sop-campo-pie') || campo;
        pie.after(err);
        campo.setAttribute('aria-invalid', 'true');
        campo.setAttribute('aria-describedby', ((campo.getAttribute('aria-describedby') || '') + ' ' + err.id).trim());
    }

    $$('form.apod-form').forEach(form => {
        const boton = $('button[type="submit"]', form);
        const textos = $$('textarea', form);
        const campos = $$('textarea, input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])', form);
        const fechaRecibido = $('input[name="recibido"]', form);
        if (fechaRecibido) fechaRecibido.max = hoyISO;
        campos.filter(c => c.tagName === 'INPUT').forEach(c => {
            const limpiar = () => { if (!revisarCampo(c, form)) limpiarError(c); };
            c.addEventListener('input', limpiar);
            c.addEventListener('change', limpiar);
        });

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
            const malos = [];
            campos.forEach(c => {
                limpiarError(c);
                const problema = revisarCampo(c, form);
                if (problema) { marcarError(c, problema); malos.push(c); }
            });
            if (malos.length) {
                ev.preventDefault();
                malos[0].focus();
                return;
            }
            if (boton && boton.disabled) { ev.preventDefault(); return; }

            // Escalar saca el ticket del panel: se confirma antes
            if (escalar && !confirmado) {
                ev.preventDefault();
                const num = (($('#section-title') || {}).textContent || '').match(/#\d+/);
                const titulo = '¿Escalar el ticket' + (num ? ' ' + num[0] : '') + '?';
                const texto = form.closest('[data-escalar-texto]')?.dataset.escalarTexto
                    || 'Pasará al líder de soporte y dejará de aparecer en tu panel. El plazo no cambia.';
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
                const enCurso = escalar ? 'Escalando…' : ($('[name="autoridad"]', form) ? 'Registrando…' : 'Enviando…');
                boton.innerHTML = '<i class="bi bi-hourglass-split" aria-hidden="true"></i> ' + enCurso;
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
        const vistos = new Set();
        const tickets = filas.filter(tr => {
            const href = $('a.sop-ticket', tr)?.getAttribute('href');
            if (!href || vistos.has(href)) return false;
            vistos.add(href);
            return true;
        }).map(tr => {
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
