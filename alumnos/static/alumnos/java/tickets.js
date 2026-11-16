/* Ayudas de las paginas de soporte del portal del alumno (nuevo ticket y detalle). Solo actua si encuentra sus piezas
   (.tk-nuevo, .tk-pagina): en cualquier otra pagina no hace nada. Viene del bloque 4 de la copia de crear_ticket. */
    // Solo actúa si encuentra sus piezas: en otras páginas no hace nada.
    (function () {
        const $ = (sel, raiz = document) => raiz.querySelector(sel);
        const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));

        // ── 1. Crear ticket: categorías como tarjetas, con el plazo de respuesta de cada una ──
        const select = $('.tk-nuevo #id_categoria');
        if (select) {
            const INFO = {
                pagos: ['bi-credit-card'], clases: ['bi-journal-bookmark'], conducta: ['bi-exclamation-triangle'],
                videos: ['bi-play-circle'], tecnico: ['bi-tools'], otro: ['bi-three-dots'],
            };
            // Dias habiles de respuesta por categoria: los manda el servidor (json_script #tk-plazos)
            const el = document.getElementById('tk-plazos');
            const PLAZOS = el ? JSON.parse(el.textContent) : {};
            const label = $('label[for="id_categoria"]');
            if (label) label.id = 'tk-categoria-label';
            const grupo = document.createElement('div');
            grupo.className = 'tk-categorias';
            grupo.setAttribute('role', 'radiogroup');
            grupo.setAttribute('aria-labelledby', 'tk-categoria-label');
            // Si llegaste desde "Repórtalo" en un video (?video=…), la categoría ya viene elegida
            if (new URLSearchParams(window.location.search).has('video') && Array.from(select.options).some(o => o.value === 'videos')) select.value = 'videos';
            Array.from(select.options).forEach(op => {
                const [icono] = INFO[op.value] || ['bi-tag'];
                const item = document.createElement('label');
                item.className = 'tk-categoria';
                item.innerHTML = `<input type="radio" name="categoria" value="${op.value.replace(/"/g, '&quot;')}">` +
                    `<i class="bi ${icono}" aria-hidden="true"></i><span></span>`;
                item.querySelector('span').textContent = op.textContent.trim();
                item.querySelector('input').checked = op.value === select.value;
                grupo.appendChild(item);
            });
            // Las tarjetas mandan el valor (mismo name "categoria"); el <select> queda oculto y sin name
            select.removeAttribute('name');
            select.hidden = true;
            select.after(grupo);
            const plazo = $('#tk-plazo');
            const pintarPlazo = () => {
                const valor = $('input[name="categoria"]:checked', grupo)?.value;
                const dias = PLAZOS[valor];
                if (plazo) plazo.innerHTML = dias ? `<i class="bi bi-clock" aria-hidden="true"></i> Te respondemos en ${dias} días hábiles.` : '';
            };
            grupo.addEventListener('change', (e) => { select.value = e.target.value; pintarPlazo(); });
            pintarPlazo();
        }

        // ── 2. Contador de caracteres en los campos con límite ──
        $$('.tk-pagina .apod-form__campo').forEach(campo => {
            const control = campo.querySelector('input[maxlength], textarea[maxlength]');
            if (!control) return;
            const max = Number(control.getAttribute('maxlength'));
            const cuenta = document.createElement('span');
            cuenta.className = 'tk-contador';
            cuenta.setAttribute('aria-hidden', 'true');
            const pie = document.createElement('div');
            pie.className = 'tk-campo-pie';
            const ayuda = campo.querySelector('small');
            if (ayuda) pie.appendChild(ayuda); else pie.appendChild(document.createElement('span'));
            pie.appendChild(cuenta);
            control.after(pie);
            const pintar = () => {
                const n = control.value.length;
                cuenta.textContent = `${n} / ${max}`;
                cuenta.classList.toggle('tk-contador--cerca', n >= max * 0.9);
            };
            control.addEventListener('input', pintar);
            pintar();
        });

        // El campo de texto crece mientras escribes (hasta un tope)
        $$('.tk-pagina textarea').forEach(t => {
            const ajustar = () => { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight + 2, 420) + 'px'; };
            t.addEventListener('input', ajustar);
        });

        // ── 3. Envío: avisa qué falta sin recargar y evita mandar dos veces ──
        $$('.tk-pagina form.apod-form').forEach(form => {
            form.addEventListener('submit', (e) => {
                $$('.tk-error', form).forEach(el => el.remove());
                $$('[aria-invalid]', form).forEach(el => el.removeAttribute('aria-invalid'));
                const vacios = $$('[required]', form).filter(c => !c.value.trim());
                if (vacios.length) {
                    e.preventDefault();
                    vacios.forEach(c => {
                        c.setAttribute('aria-invalid', 'true');
                        const err = document.createElement('p');
                        err.className = 'tk-error';
                        err.id = c.id + '-error';
                        err.textContent = {id_titulo: 'Escribe un asunto.', id_descripcion: 'Cuéntanos qué pasó.', id_texto: 'Escribe tu respuesta.'}[c.id] || 'Completa este campo.';
                        c.setAttribute('aria-describedby', [c.getAttribute('aria-describedby'), err.id].filter(Boolean).join(' '));
                        (c.nextElementSibling && c.nextElementSibling.classList.contains('tk-campo-pie') ? c.nextElementSibling : c).after(err);
                    });
                    vacios[0].focus();
                    return;
                }
                const boton = $('button[type="submit"]', form);
                if (boton) {
                    boton.disabled = true;
                    boton.innerHTML = '<i class="bi bi-hourglass-split" aria-hidden="true"></i> Enviando…';
                }
            });
            // Ctrl + Enter envía desde el campo de texto
            $$('textarea', form).forEach(t => t.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); }
            }));
            // Al escribir, se quita el aviso de ese campo
            form.addEventListener('input', (e) => {
                if (!e.target.value.trim()) return;
                e.target.removeAttribute('aria-invalid');
                document.getElementById(e.target.id + '-error')?.remove();
            });
        });
    })();
