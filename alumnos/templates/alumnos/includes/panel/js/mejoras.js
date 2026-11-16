{# Parte de alumnos/Alumno_pag1.html: se incluye dentro de su propio <script> al final de la pagina (no es un archivo estatico). #}
{# Mejoras de uso del portal: todo sale de lo que el servidor ya pinto; si algo no esta, esa parte no se hace. #}
        // Todo sale de lo que el servidor ya pintó en la página: no hay datos nuevos ni llamadas extra.
        // Si algo no está (otra página del portal, sin paquete, etc.), esa parte simplemente no se hace.
        (function () {
            if (!document.querySelector('.dashboard-view')) return;

            const $ = (sel, raiz = document) => raiz.querySelector(sel);

            // La URL recuerda la vista (#view-...), pero el navegador además salta hasta ese id al cargar:
            // se vuelve arriba para que la vista se vea desde su título.
            window.addEventListener('load', () => {
                if (/^#(view|tab)-/.test(window.location.hash)) setTimeout(() => window.scrollTo(0, 0), 0);
            });
            const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
            const numero = (texto) => { const n = parseInt(String(texto).replace(/\D+/g, ''), 10); return Number.isNaN(n) ? null : n; };
            const escapar = (texto) => String(texto).replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'})[c]);

            let plan = null;
            try { plan = JSON.parse($('#plan-activo').textContent); } catch (e) {}
            const premium = Boolean(plan && plan.premium);

            // ── Paquetes: clases que quedan y días para que venza ──
            const hoy = new Date(new Date().toLocaleDateString('en-CA', {timeZone: 'America/Santiago'}) + 'T00:00:00');
            const diasHasta = (ddmmaaaa) => {
                const [d, m, a] = ddmmaaaa.split('-').map(Number);
                return Math.round((new Date(a, m - 1, d) - hoy) / 86400000);
            };
            let clasesDisponibles = 0;
            $$('#view-plans .pp-card').forEach(card => {
                const quedan = numero($('.pp-price', card)?.textContent);
                const total = numero($('.pp-period', card)?.textContent);
                if (quedan === null) return;
                clasesDisponibles += quedan;
                if (!total) return;

                const pct = Math.max(0, Math.min(100, Math.round(quedan / total * 100)));
                const medidor = document.createElement('div');
                medidor.className = 'pp-meter' + (pct <= 25 ? ' pp-meter--bajo' : '');
                medidor.setAttribute('role', 'meter');
                medidor.setAttribute('aria-valuemin', '0');
                medidor.setAttribute('aria-valuemax', String(total));
                medidor.setAttribute('aria-valuenow', String(quedan));
                medidor.setAttribute('aria-label', `Te quedan ${quedan} de ${total} clases`);
                medidor.innerHTML = `<span style="width:${pct}%"></span>`;
                $('.pp-price-box', card).after(medidor);

                const vence = ($('.pp-billing', card)?.textContent || '').match(/(\d{2}-\d{2}-\d{4})/);
                if (!vence) return;
                const dias = diasHasta(vence[1]);
                const chip = document.createElement('span');
                chip.className = 'pp-vence' + (dias <= 7 ? ' pp-vence--pronto' : '');
                chip.innerHTML = '<i class="bi bi-hourglass-split" aria-hidden="true"></i> ' +
                    (dias < 0 ? 'Vencido' : dias === 0 ? 'Vence hoy' : `Vence en ${dias} día${dias === 1 ? '' : 's'}`);
                $('.pp-title', card).after(chip);
            });

            // ── Banner: fecha de hoy, próximo paso y tarjeta de clases ──
            const hoyTexto = new Date().toLocaleDateString('es-CL', {weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Santiago'});
            const etiquetaHoy = $('#ap-hoy');
            if (etiquetaHoy) etiquetaHoy.textContent = hoyTexto.charAt(0).toUpperCase() + hoyTexto.slice(1);

            const inscritas = numero($('.stat-card[data-ir="inscritas"] .stat-info h3')?.textContent) || 0;
            const paquetes = $$('#view-plans .pp-card');
            const textoPaso = $('#ap-proximo-texto');
            const botonPaso = $('#ap-proximo-btn');
            if (textoPaso && botonPaso) {
                const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
                let texto, boton, accion;
                if (!paquetes.length) {
                    texto = 'Para reservar clases necesitas un paquete con el profesor que elijas.';
                    boton = 'Ver planes y precios'; accion = () => { window.location.href = '{% url 'planes' %}'; };
                } else if (clasesDisponibles === 0) {
                    texto = 'Ya usaste todas las clases de tu paquete.';
                    boton = 'Comprar más clases'; accion = () => { window.location.href = '{% url 'planes' %}'; };
                } else if (inscritas === 0) {
                    texto = `Tienes ${plural(clasesDisponibles, 'clase', 'clases')} por reservar. Elige un horario y agenda la primera.`;
                    boton = 'Reservar una clase'; accion = () => window.requestClassAccess();
                } else {
                    texto = `Tienes ${plural(inscritas, 'clase agendada', 'clases agendadas')} y ${plural(clasesDisponibles, 'clase', 'clases')} por reservar.`;
                    boton = 'Ver mis clases'; accion = () => window.switchView('view-my-classes');
                }
                textoPaso.textContent = texto;
                botonPaso.textContent = boton;
                botonPaso.addEventListener('click', accion);
                botonPaso.hidden = false;
            }

            // Tarjeta de clases: un círculo por clase del paquete; los usados quedan "perforados".
            const tarjeta = $('#ap-tarjeta-clases');
            const primera = paquetes[0];
            if (tarjeta && primera) {
                const quedan = numero($('.pp-price', primera)?.textContent) || 0;
                const total = numero($('.pp-period', primera)?.textContent) || quedan;
                const nombre = ($('.pp-title', primera)?.textContent || 'Paquete').trim();
                const detalle = ($('.pp-billing', primera)?.textContent || '').trim();
                const profesor = detalle.split('·')[0].replace(/^Con\s+/i, '').trim();
                const vence = detalle.match(/(\d{2}-\d{2}-\d{4})/);
                const dias = vence ? diasHasta(vence[1]) : null;
                const usadas = Math.max(0, total - quedan);
                const circulos = total <= 12
                    ? `<span class="tc-holes" aria-hidden="true">${Array.from({length: total}, (_, i) =>
                        `<span class="tc-hole${i < usadas ? ' tc-hole--usada' : ''}" style="--i:${i}"></span>`).join('')}</span>`
                    : `<span class="tc-barra" aria-hidden="true"><span style="width:${Math.round(quedan / total * 100)}%"></span></span>`;
                const textoVence = dias === null ? '' : dias < 0 ? 'Vencido' : dias === 0 ? 'Vence hoy'
                    : `Vence en ${dias} día${dias === 1 ? '' : 's'}`;
                tarjeta.innerHTML =
                    `<span class="tc-top"><span class="tc-plan">${escapar(nombre)}</span>` +
                    (textoVence ? `<span class="tc-vence${dias !== null && dias <= 7 ? ' tc-vence--pronto' : ''}">${escapar(textoVence)}</span>` : '') +
                    `</span>${circulos}` +
                    `<span class="tc-cuenta"><strong>${quedan}</strong> de ${total} clases por usar</span>` +
                    `<span class="tc-pie"><span>${profesor ? 'Con ' + escapar(profesor) : ''}</span>` +
                    (paquetes.length > 1 ? `<span>+${paquetes.length - 1} paquete${paquetes.length > 2 ? 's' : ''}</span>` : '') + `</span>`;
                tarjeta.setAttribute('aria-label', `${nombre}: te quedan ${quedan} de ${total} clases${textoVence ? '. ' + textoVence : ''}. Ver mis paquetes`);
                tarjeta.addEventListener('click', () => window.switchView('view-plans'));
                tarjeta.hidden = false;
            }

            {% if not es_menor %}{# el menor no reserva: lo hace su apoderado (el servidor tambien lo impide) #}
            // ── Agenda: horarios libres de los próximos días, para reservar desde el Dashboard ──
            const grilla = $('#view-dashboard .main-dashboard-grid');
            let profesores = [];
            try { profesores = JSON.parse($('#profesores-data').textContent); } catch (e) {}
            if (grilla) {
                let derecha = $('.dashboard-right-panel', grilla);
                if (!derecha) {  // sin anuncio (p. ej. un menor): igual se crea la columna para la agenda
                    derecha = document.createElement('div');
                    derecha.className = 'dashboard-right-panel';
                    grilla.appendChild(derecha);
                }
                const hoyIso = new Date().toLocaleDateString('en-CA', {timeZone: 'America/Santiago'});
                const libres = profesores.flatMap(p => (p.horarios || []).map(h => ({...h, profesor: p.name})))
                    .filter(h => h.fecha >= hoyIso)
                    .sort((x, y) => (x.fecha + x.hora).localeCompare(y.fecha + y.hora));
                const fechaCorta = (iso, op) => new Date(iso + 'T12:00:00').toLocaleDateString('es-CL', op).replace('.', '');
                const items = libres.slice(0, 5).map(h => {
                    const ddmm = h.fecha.split('-').reverse().join('/');
                    return `<li><button type="button" class="ag-item" data-sesion="${Number(h.id_sesion)}" ` +
                        `data-asig="${escapar(h.asignatura)}" data-fechahora="${escapar(ddmm + ' ' + h.hora)}" ` +
                        `aria-label="${escapar(`Reservar ${h.asignatura} con ${h.profesor}, ${fechaCorta(h.fecha, {weekday: 'long', day: 'numeric', month: 'long'})} a las ${h.hora}`)}">` +
                        `<span class="ag-fecha"><span>${escapar(fechaCorta(h.fecha, {weekday: 'short'}))}</span><strong>${Number(h.fecha.slice(8))}</strong></span>` +
                        `<span class="ag-info"><strong>${escapar(h.hora)} h</strong><span>${escapar(h.asignatura)} con ${escapar(h.profesor)}</span></span>` +
                        `<i class="bi bi-plus-circle ag-accion" aria-hidden="true"></i></button></li>`;
                }).join('');
                const agenda = document.createElement('section');
                agenda.className = 'agenda-libre';
                agenda.setAttribute('aria-labelledby', 'agenda-libre-titulo');
                agenda.innerHTML = `<h3 id="agenda-libre-titulo">Horarios libres</h3>` +
                    `<p class="agenda-sub">Próximos 7 días, de todos tus profesores</p>` +
                    (items ? `<ul>${items}</ul>` + (libres.length > 5 ? `<button type="button" class="agenda-mas">Ver los ${libres.length} horarios</button>` : '')
                           : `<p class="agenda-vacia">No hay horarios libres esta semana. Revisa el catálogo o pide una clase extra.</p>`);
                derecha.prepend(agenda);
                agenda.addEventListener('click', (e) => {
                    const item = e.target.closest('.ag-item');
                    if (item) return window.confirmarReservaSesion(item.dataset.sesion, item.dataset.asig, item.dataset.fechahora);
                    if (e.target.closest('.agenda-mas')) irA.profesores();
                });
            }

            {% endif %}

            // ── Tarjetas de estadística: llevan a su sección ──
            const irA = {
                inscritas: () => window.switchView('view-my-classes'),
                catalogo: () => window.requestClassAccess(),
                profesores: () => {
                    $('.tab-btn[data-tab="tab-profesores"]')?.click();
                    $('#view-dashboard .results-section')?.scrollIntoView({behavior: 'smooth', block: 'start'});
                },
            };
            $$('.stat-card[data-ir]').forEach(card => {
                const ir = irA[card.dataset.ir];
                if (!ir) return;
                card.addEventListener('click', ir);
                card.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ir(); }
                });
            });

            // ── Menú: plan en la ficha del alumno y candado en lo premium si no hay paquete vigente ──
            const rol = $('.sb-user-role');
            if (rol && plan && plan.nombre) rol.textContent = `Plan ${plan.nombre}`;
            if (!premium) {
                $$('.sidebar-view-btn[data-view="view-progress"]{% if not es_menor %}, .sidebar-view-btn[data-view="view-inbox"]{% endif %}').forEach(btn => {
                    btn.classList.add('is-locked');
                    btn.insertAdjacentHTML('beforeend', '<i class="bi bi-lock-fill sb-lock" aria-hidden="true"></i>');
                    btn.setAttribute('title', 'Requiere un paquete de clases vigente');
                });
            }

            {% if not es_menor %}{# el menor no tiene buzón: nada de su código llega a su página #}
            // ── Buzón: toda la fila del contacto abre la conversación (no solo el botón "Escribir") ──
            $$('#chat-contacts-list .chat-contact-item').forEach(fila => {
                fila.addEventListener('click', (e) => {
                    if (e.target.closest('button, a, input')) return;
                    if (fila.requestSubmit) fila.requestSubmit(); else fila.submit();
                });
            });

            // No leídos: número en el menú, junto a "Buzón de dudas"
            const noLeidos = $$('#chat-contacts-list .chat-contact-item.unread').length;
            const botonBuzon = $('.sidebar-view-btn[data-view="view-inbox"]');
            if (noLeidos && botonBuzon && premium) {
                botonBuzon.insertAdjacentHTML('beforeend',
                    `<span class="sb-contador" aria-label="${noLeidos} conversación${noLeidos === 1 ? '' : 'es'} sin leer">${noLeidos}</span>`);
            }

            // Móvil: con una conversación abierta se ve solo el chat; "Volver" muestra la lista
            const bandeja = $('.inbox-layout');
            const cabeceraChat = $('.chat-main .chat-header');
            if (bandeja && cabeceraChat) {
                bandeja.classList.add('inbox-layout--conversacion');
                const volver = document.createElement('button');
                volver.type = 'button';
                volver.className = 'chat-volver';
                volver.setAttribute('aria-label', 'Volver a la lista de profesores');
                volver.innerHTML = '<i class="bi bi-chevron-left" aria-hidden="true"></i>';
                volver.addEventListener('click', () => bandeja.classList.toggle('inbox-layout--lista'));
                cabeceraChat.prepend(volver);
            }
            {% endif %}

            // ── Dashboard: sin tutores reales, la pestaña "Tutores" solo confundía ──
            const contTutores = $('#dashboard-tutors-container');
            if (contTutores && !contTutores.children.length) {
                $('.dashboard-tabs')?.setAttribute('hidden', '');
                const titulo = $('#view-dashboard .results-section > h2');
                if (titulo) titulo.textContent = 'Profesores';
            }

            // ── Dashboard: barra con los filtros activos (temas de interés y favoritos), cada uno se quita con un toque ──
            const barra = $('#filtros-activos');
            const pintarFiltros = () => {
                if (!barra) return;
                const temas = $$('.topic-tag.selected').map(b => b.dataset.topic);
                const chips = temas.map(t =>
                    `<button type="button" class="filtro-chip" data-tema="${escapar(t)}" aria-label="Quitar filtro ${escapar(t)}">${escapar(t)} <i class="bi bi-x" aria-hidden="true"></i></button>`).join('');
                const cuantos = $$('#dashboard-teachers-container .teacher-card').length;
                barra.innerHTML =
                    `<button type="button" class="filtro-chip filtro-chip--fav" aria-pressed="${Boolean(window.soloFavoritos)}">` +
                    `<i class="bi ${window.soloFavoritos ? 'bi-star-fill' : 'bi-star'}" aria-hidden="true"></i> Solo favoritos</button>` +
                    chips +
                    `<button type="button" class="filtro-editar">${temas.length ? 'Cambiar temas' : 'Filtrar por temas'}</button>` +
                    `<span class="filtro-cuenta">${cuantos} profesor${cuantos === 1 ? '' : 'es'}</span>`;
                barra.hidden = false;
            };
            if (barra) {
                barra.addEventListener('click', (e) => {
                    const chip = e.target.closest('.filtro-chip');
                    if (chip && chip.classList.contains('filtro-chip--fav')) {
                        window.soloFavoritos = !window.soloFavoritos;
                    } else if (chip) {
                        const tag = $$('.topic-tag').find(b => b.dataset.topic === chip.dataset.tema);
                        if (tag) tag.classList.remove('selected');
                        try { localStorage.setItem(claveLocal('selected-topics'), JSON.stringify($$('.topic-tag.selected').map(b => b.dataset.topic))); } catch (er) {}
                    } else if (e.target.closest('.filtro-editar')) {
                        $('#dashboard-setup-btn')?.click();
                        return;
                    } else return;
                    window.renderDashboardContent();
                });
                // Se repinta cada vez que cambia la lista (búsqueda, temas, favoritos)
                const listaProfes = $('#dashboard-teachers-container');
                if (listaProfes) new MutationObserver(pintarFiltros).observe(listaProfes, {childList: true});
                pintarFiltros();
            }

            // ── Atajos de teclado ──
            // Esc cierra lo que esté abierto (modal de temas, de horarios o el menú en móvil).
            // "/" lleva al buscador del Dashboard, como en la mayoría de las apps.
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    if (window.Swal && Swal.isVisible && Swal.isVisible()) return;  // SweetAlert se cierra solo
                    if ($('#interests-modal.open')) { $('#close-modal-btn')?.click(); return; }
                    if ($('#modal-horarios-sesiones.open')) { window.cerrarModalHorarios(); return; }
                    if ($('.sidebar-menu.active') && window.closeSidebar) window.closeSidebar();
                    return;
                }
                const escribiendo = e.target.closest('input, textarea, select, [contenteditable="true"]');
                if (e.key === '/' && !escribiendo && !e.ctrlKey && !e.metaKey && !e.altKey) {
                    const buscador = $('#dashboard-search-input');
                    if (!buscador) return;
                    e.preventDefault();
                    window.switchView('view-dashboard');
                    buscador.focus();
                }
            });
        })();
