/* Panel docente: mejoras de uso (de la copia: bloque 5). Titulo de la barra superior segun la seccion, resumen del dia,
   buscador Ctrl+K con las secciones del profesor, agenda, vista previa de la foto, datos del video antes de subirlo y
   la ventana de ayuda del buzon. Todo sale de lo que el servidor ya pinto; cada parte revisa que su elemento exista,
   asi que se activa sola cuando la pagina lo trae. Va al final de panel_profesor.html (usa switchSection y closeUploadModal). */
    // Todo sale de lo que el servidor ya pintó en la página: no hay llamadas nuevas.
    // Si algo no existe (otra página del portal), esa parte simplemente no se hace.
    (function () {
        if (!document.querySelector('.prof-section')) return;
        const $ = (sel, raiz = document) => raiz.querySelector(sel);
        const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
        const esc = window.escaparHtml;
        const sinTildes = (t) => String(t || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

        // ── 1. La barra superior dice en qué sección estás (antes decía siempre "Panel docente") ──
        const TITULOS = {
            inicio: ['Inicio', 'Resumen de tu día'],
            clases: ['Clases solicitadas', 'Alumnos inscritos en tus materias'],
            agenda: ['Mi agenda', 'Tu horario semanal y tus reservas'],
            buzon: ['Buzón de alumnos', 'Conversa con tus estudiantes'],
            grabaciones: ['Videos de apoyo', 'Tu biblioteca y lo que debes compartir'],
            streaming: ['Sala de streaming', 'Clases 1 a 1 en vivo'],
            perfil: ['Mi perfil', 'Tus datos y tu foto'],
            saldo: ['Saldo y pagos', 'Ganancias, retiros y liquidaciones'],
            resenas: ['Mis reseñas', 'Lo que opinan tus alumnos'],
            ayuda: ['Ayuda y soporte', 'Tickets y privacidad'],
        };
        let anterior = null;
        function alCambiarSeccion(inicial) {
            const activa = $('.prof-section.active');
            const id = activa && activa.id.replace('sec-', '');
            if (!id || id === anterior) return;
            anterior = id;
            const t = TITULOS[id];
            if (t) {
                const h = $('#section-title'), p = $('#section-subtitle');
                if (h) h.textContent = t[0];
                if (p) p.textContent = t[1];
                document.title = `${t[0]} | LBWUS Docente`;
            }
            $$('.nav-item[data-seccion]').forEach(a => {
                if (a.dataset.seccion === id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
            });
            // Al cargar no se toca la URL: el bloque 4 la lee después para volver a la sección guardada
            if (inicial === true) return;
            // La URL recuerda la sección también cuando se llega desde un botón (no solo desde el menú)
            if (window.location.hash !== '#' + id) history.replaceState(null, '', window.location.pathname + window.location.search + '#' + id);
            window.scrollTo(0, 0);
        }
        $$('.prof-section').forEach(sec => new MutationObserver(() => alCambiarSeccion()).observe(sec, {attributes: true, attributeFilter: ['class']}));
        alCambiarSeccion(true);
        // El navegador salta hasta el id del #hash al cargar: se vuelve arriba
        window.addEventListener('load', () => { if (window.location.hash) setTimeout(() => window.scrollTo(0, 0), 0); });

        // ── 2. Inicio: fecha de hoy y resumen del día ──
        const hoy = new Date().toLocaleDateString('es-CL', {weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Santiago'});
        const etiquetaHoy = $('#prof-hoy');
        if (etiquetaHoy) etiquetaHoy.textContent = hoy.charAt(0).toUpperCase() + hoy.slice(1);
        const resumen = $('#prof-resumen-hoy');
        if (resumen) {
            const clasesHoy = $$('#sec-inicio .prof-schedule-item');
            if (clasesHoy.length) {
                const hora = (clasesHoy[0].querySelector('.prof-schedule-time')?.textContent || '').trim();
                resumen.textContent = `Hoy tienes ${clasesHoy.length} clase${clasesHoy.length === 1 ? '' : 's'}` +
                    (hora ? `. La primera es a las ${hora}.` : '.');
            } else {
                resumen.textContent = 'Hoy no tienes clases agendadas. Revisa tu agenda para ofrecer más horarios.';
            }
        }

        // Gráfico sin datos: se dice en palabras en vez de mostrar cinco barras vacías
        const barras = $$('#sec-inicio .prof-chart-bar');
        if (barras.length && barras.every(b => parseFloat(b.style.height) === 0)) {
            const cont = $('#sec-inicio .prof-chart-container');
            if (cont) {
                cont.classList.add('prof-chart--vacio');
                cont.insertAdjacentHTML('beforeend', '<p class="prof-chart-vacio"><i class="bi bi-bar-chart" aria-hidden="true"></i> Aún no recibes solicitudes en estos meses.</p>');
            }
        }

        // ── 3. Buscador (Ctrl + K): secciones del profesor. Antes mostraba las del admin y llevaba al panel admin ──
        // Ajuste para este proyecto: Mis resenas y Ayuda son paginas con su enlace en el menu (#nav-X), no secciones del panel;
        // solo se ofrecen los destinos que existen (Ayuda no esta si el profesor no tiene url_ayuda).
        const SECCIONES = Object.entries(TITULOS).map(([id, [titulo, sub]]) => ({
            id, titulo, sub,
            icono: ($(`#menu-${id} i`)?.className || $(`#nav-${id} i`)?.className || 'bi bi-circle').replace(/^bi\s+/, ''),
        })).filter(s => document.getElementById('sec-' + s.id) || document.getElementById('nav-' + s.id));
        const fila = (s) => `<div class="search-result-item" role="option" tabindex="0" data-ir="${esc(s.id)}">` +
            `<i class="bi ${esc(s.icono)}" aria-hidden="true"></i><span>${esc(s.titulo)}</span>` +
            `<span class="search-result-type">${esc(s.sub)}</span></div>`;
        window.navigateFromSearch = (id) => {
            window.closeSearchModal();
            if (document.getElementById('sec-' + id)) return window.switchSection(id);
            // Ajuste para este proyecto: si no es una seccion del panel, se va al enlace de su menu
            const enlace = document.getElementById('nav-' + id);
            if (enlace) window.location.href = enlace.href;
        };
        window.handleGlobalSearch = () => {
            const caja = $('#search-modal-results');
            if (!caja) return;
            const q = sinTildes($('#search-modal-input')?.value.trim());
            const lista = q ? SECCIONES.filter(s => sinTildes(`${s.titulo} ${s.sub}`).includes(q)) : SECCIONES;
            caja.innerHTML = lista.length
                ? `<div class="search-section-label">${q ? 'Resultados' : 'Secciones'}</div>${lista.map(fila).join('')}`
                : `<div class="search-section-label">Búsqueda</div><p class="search-sin-resultados">No hay secciones que calcen con "${esc(q)}".</p>`;
        };
        // Al abrir el buscador se muestran todas las secciones (antes quedaban los resultados de la búsqueda anterior)
        const abrirOriginal = window.openSearchModal;
        if (abrirOriginal) window.openSearchModal = () => { abrirOriginal(); window.handleGlobalSearch(); };
        const cajaResultados = $('#search-modal-results');
        if (cajaResultados) {
            cajaResultados.addEventListener('click', (e) => {
                const item = e.target.closest('.search-result-item[data-ir]');
                if (item) window.navigateFromSearch(item.dataset.ir);
            });
            cajaResultados.addEventListener('keydown', (e) => {
                const item = e.target.closest('.search-result-item[data-ir]');
                if (item && e.key === 'Enter') window.navigateFromSearch(item.dataset.ir);
            });
            // Enter en el campo abre el primer resultado
            $('#search-modal-input')?.addEventListener('keydown', (e) => {
                if (e.key !== 'Enter') return;
                const primero = $('#search-modal-results .search-result-item[data-ir]');
                if (primero) window.navigateFromSearch(primero.dataset.ir);
            });
            window.handleGlobalSearch();
        }

        // ── 4. Agenda: "Hasta" siempre después de "Desde", con la duración a la vista ──
        const desde = $('#agenda-desde'), hasta = $('#agenda-hasta');
        if (desde && hasta) {
            const formAgenda = desde.closest('form');
            const nota = document.createElement('p');
            nota.className = 'agenda-duracion';
            nota.setAttribute('aria-live', 'polite');
            formAgenda.querySelector('.prof-form-row')?.after(nota);
            const horas = (v) => parseInt(v, 10);
            const pintar = () => {
                const d = horas(hasta.value) - horas(desde.value);
                nota.classList.toggle('agenda-duracion--error', d <= 0);
                nota.innerHTML = d > 0
                    ? `<i class="bi bi-clock" aria-hidden="true"></i> ${d} hora${d === 1 ? '' : 's'}: ${d} bloque${d === 1 ? '' : 's'} de 60 minutos para reservar.`
                    : '<i class="bi bi-exclamation-circle" aria-hidden="true"></i> "Hasta" tiene que ser después de "Desde".';
            };
            const ajustar = () => {
                if (horas(hasta.value) <= horas(desde.value)) {
                    const siguiente = Array.from(hasta.options).find(o => horas(o.value) > horas(desde.value));
                    if (siguiente) hasta.value = siguiente.value;
                }
                pintar();
            };
            desde.addEventListener('change', ajustar);
            hasta.addEventListener('change', pintar);
            formAgenda.addEventListener('submit', (e) => {
                if (horas(hasta.value) <= horas(desde.value)) { e.preventDefault(); pintar(); hasta.focus(); }
            });
            ajustar();
        }

        // ── 5. Perfil: vista previa de la foto antes de guardar ──
        const inputFoto = $('#prof-foto'), vistaFoto = $('#prof-foto-preview'), textoBotonFoto = $('#prof-foto-texto-boton');
        if (inputFoto && vistaFoto) {
            if (vistaFoto.querySelector('img') && textoBotonFoto) textoBotonFoto.textContent = 'Cambiar foto';
            inputFoto.addEventListener('change', () => {
                const archivo = inputFoto.files && inputFoto.files[0];
                if (!archivo || !archivo.type.startsWith('image/')) return;
                const img = document.createElement('img');
                img.alt = 'Vista previa de tu foto';
                img.src = URL.createObjectURL(archivo);
                vistaFoto.replaceChildren(img);
                if (textoBotonFoto) textoBotonFoto.textContent = 'Cambiar foto';
            });
        }

        // ── 6. Subir video: nombre, peso y duración antes de enviar (evita esperar la subida para enterarse) ──
        const inputVideo = $('#upload-file'), infoVideo = $('#upload-file-info');
        if (inputVideo && infoVideo) {
            const MAX_MB = 500, MAX_MIN = 30;
            const mostrar = (texto, error) => {
                infoVideo.hidden = !texto;
                infoVideo.textContent = texto || '';
                infoVideo.classList.toggle('upload-archivo-info--error', Boolean(error));
                inputVideo.setCustomValidity(error ? texto : '');
            };
            inputVideo.addEventListener('change', () => {
                const archivo = inputVideo.files && inputVideo.files[0];
                if (!archivo) return mostrar('');
                const mb = archivo.size / 1048576;
                const base = `${archivo.name} · ${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
                if (mb > MAX_MB) return mostrar(`${base}. Pesa más de ${MAX_MB} MB: comprímelo o córtalo antes de subirlo.`, true);
                mostrar(base);
                const v = document.createElement('video');
                v.preload = 'metadata';
                v.onloadedmetadata = () => {
                    URL.revokeObjectURL(v.src);
                    const min = v.duration / 60;
                    if (min > MAX_MIN) mostrar(`${base} · ${Math.round(min)} min. Dura más de ${MAX_MIN} minutos: córtalo antes de subirlo.`, true);
                    else mostrar(`${base} · ${Math.floor(min)}:${String(Math.round(v.duration % 60)).padStart(2, '0')} min`);
                };
                v.src = URL.createObjectURL(archivo);
            });
        }
        // La ventana de subida se cierra con Esc o tocando fuera
        const modalSubida = $('#profe-upload-modal');
        if (modalSubida) {
            modalSubida.addEventListener('click', (e) => { if (e.target === modalSubida) window.closeUploadModal(); });
            document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && modalSubida.classList.contains('open')) window.closeUploadModal(); });
        }

        // ── 7. Buzón: "Cómo funcionan los mensajes" en una ventana ──
        const dialogo = $('#dialogo-mensajes'), botonAyuda = $('.btn-ayuda-mensajes');
        if (dialogo && botonAyuda && dialogo.showModal) {
            botonAyuda.addEventListener('click', () => dialogo.showModal());
            dialogo.addEventListener('click', (e) => { if (e.target === dialogo) dialogo.close(); });
            dialogo.addEventListener('close', () => botonAyuda.focus());
        }
    })();
