{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── GESTIÓN DE MODAL DE HORARIOS Y RESERVAS DE SESIONES ──
        // "16/11/2026" -> {dia: 'lun', num: '16', mes: 'nov', largo: 'Lunes · 16/11/2026'}, ya escapado para el html.
        // Mismo formato que el perfil del profesor y "Mis clases" (Sesión: dd/mm/aaaa).
        function partesDeFecha(fechaDdMmAaaa) {
            const [d, m, a] = String(fechaDdMmAaaa).split('/').map(Number);
            const fecha = new Date(a, m - 1, d);
            if (Number.isNaN(fecha.getTime())) {
                const safeTal = escaparHtml(fechaDdMmAaaa);
                return {dia: '', num: '', mes: '', largo: safeTal};
            }
            const parte = opciones => fecha.toLocaleDateString('es-CL', opciones).replace('.', '');
            const diaLargo = parte({weekday: 'long'});
            return {
                dia: escaparHtml(parte({weekday: 'short'})),
                num: String(d),
                mes: escaparHtml(parte({month: 'short'})),
                largo: escaparHtml(`${diaLargo.charAt(0).toUpperCase() + diaLargo.slice(1)} · ${fechaDdMmAaaa}`),
            };
        }

        // idInscripcion: modo "mover reserva" (reprogramar) en vez de reservar una nueva.
        function abrirModalHorarios(idClase, nombreAsignatura, nombreProfesor, idInscripcion = null) {
            const modal = document.getElementById('modal-horarios-sesiones');
            if (!modal) return;

            document.getElementById('modal-horarios-titulo').innerText = idInscripcion ? `Reprogramar: ${nombreAsignatura}` : `${nombreAsignatura}`;
            document.getElementById('modal-horarios-profesor').innerText = `Profesor(a): ${nombreProfesor}`;

            const loadingEl = document.getElementById('modal-horarios-loading');
            const emptyEl = document.getElementById('modal-horarios-empty');
            const listaEl = document.getElementById('modal-horarios-lista');

            loadingEl.style.display = 'block';
            emptyEl.style.display = 'none';
            listaEl.style.display = 'none';
            listaEl.innerHTML = '';

            modal.classList.add('open');

            fetch(`{% url 'sesiones_disponibles' %}?clase_id=${idClase}`)
                .then(res => res.json())
                .then(data => {
                    loadingEl.style.display = 'none';
                    if (data.success && data.sesiones && data.sesiones.length > 0) {
                        listaEl.style.display = 'flex';
                        // Lo que vale para todos los horarios se dice una vez, arriba (no en cada tarjeta).
                        const primera = data.sesiones[0];
                        const modalidad = String(primera.modalidad || '');
                        const precioUnico = new Set(data.sesiones.map(s => s.precio_formateado)).size === 1;
                        const safeNota = [
                            idInscripcion ? 'Reprogramar no usa otra clase de tu paquete' : 'Cada reserva usa 1 clase de tu paquete',
                            `${escaparHtml(modalidad.charAt(0).toUpperCase() + modalidad.slice(1))} · ${Number(primera.duracion_minutos) || 0} min`,
                            precioUnico ? escaparHtml(primera.precio_formateado) : '',
                        ].filter(Boolean).join(' · ');
                        listaEl.innerHTML = `<p class="horarios-nota"><i class="bi bi-info-circle" aria-hidden="true"></i>${safeNota}</p>` + data.sesiones.map(s => {
                            const safeIdSesion = Number(s.id_sesion) || 0;
                            const safeAsignatura = escaparHtml(s.asignatura);
                            const safeFecha = escaparHtml(s.fecha_formateada);
                            const safeHora = escaparHtml(s.hora_formateada);
                            const safePrecio = precioUnico ? '' : ` · ${escaparHtml(s.precio_formateado)}`;
                            const safeDuracion = Number(s.duracion_minutos) || 0;
                            const safeCupos = Number(s.cupos_disponibles) || 0;
                            const safePartes = partesDeFecha(s.fecha_formateada);
                            const pocos = safeCupos <= 2 ? ' horario__cupos--pocos' : '';

                            const btnHtml = s.ya_inscrito
                                ? `<button class="ap-btn-enrolled" disabled><i class="bi bi-check-circle-fill" aria-hidden="true"></i> Ya reservado</button>`
                                : idInscripcion
                                ? `<button class="btn-principal btn-mover-sesion" data-id="${safeIdSesion}" data-asig="${safeAsignatura}" data-fechahora="${safeFecha} ${safeHora}" data-inscripcion="${idInscripcion}"><i class="bi bi-calendar2-check" aria-hidden="true"></i> Mover a este horario</button>`
                                : `<button class="btn-principal btn-reservar-sesion" data-id="${safeIdSesion}" data-asig="${safeAsignatura}" data-fechahora="${safeFecha} ${safeHora}"><i class="bi bi-bookmark-plus-fill" aria-hidden="true"></i> Reservar este horario</button>`;

                            return `
                                <article class="horario sesion-item-card${s.ya_inscrito ? ' horario--reservado' : ''}">
                                    <div class="reserva-fecha" aria-hidden="true">
                                        <span class="reserva-fecha__dia">${safePartes.dia}</span>
                                        <span class="reserva-fecha__num">${safePartes.num}</span>
                                        <span class="reserva-fecha__mes">${safePartes.mes}</span>
                                    </div>
                                    <div>
                                        <p class="horario__titulo">${safePartes.largo}</p>
                                        <p class="horario__meta">
                                            <span><i class="bi bi-clock" aria-hidden="true"></i> ${safeHora} (${safeDuracion} min)${safePrecio}</span>
                                            <span class="horario__cupos${pocos}"><i class="bi bi-people-fill" aria-hidden="true"></i> ${safeCupos} cupo${safeCupos === 1 ? '' : 's'} disponible${safeCupos === 1 ? '' : 's'}</span>
                                        </p>
                                    </div>
                                    <div class="horario__accion">${btnHtml}</div>
                                </article>
                            `;
                        }).join('');

                        listaEl.querySelectorAll('.btn-reservar-sesion').forEach(btn => {
                            btn.addEventListener('click', function() {
                                confirmarReservaSesion(
                                    this.dataset.id,
                                    this.dataset.asig,
                                    this.dataset.fechahora
                                );
                            });
                        });
                    } else {
                        emptyEl.style.display = 'block';
                    }
                })
                .catch(err => {
                    console.error('Error al cargar horarios:', err);
                    loadingEl.style.display = 'none';
                    emptyEl.style.display = 'block';
                    emptyEl.querySelector('p').innerText = 'Ocurrió un error al cargar los horarios disponibles.';
                });
        }

        function cerrarModalHorarios() {
            const modal = document.getElementById('modal-horarios-sesiones');
            if (modal) modal.classList.remove('open');
        }

        const modalHorariosOverlay = document.getElementById('modal-horarios-sesiones');
        if (modalHorariosOverlay) {
            modalHorariosOverlay.addEventListener('click', (e) => {
                if (e.target === modalHorariosOverlay) cerrarModalHorarios();
            });
        }

        function confirmarReservaSesion(idSesion, nombreAsignatura, fechaHora) {
            const safeAsig = window.escaparHtml ? window.escaparHtml(nombreAsignatura) : nombreAsignatura;
            const safeFecha = window.escaparHtml ? window.escaparHtml(fechaHora) : fechaHora;
            Swal.fire({
                title: 'Confirmar Reserva de Horario',
                html: `¿Deseas reservar tu cupo para la sesión de <b>"${safeAsig}"</b>?<br><br><span style="color:var(--primary); font-weight:600;"><i class="bi bi-clock"></i> ${safeFecha}</span>`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, Reservar Cupo',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: 'var(--primary)',
                cancelButtonColor: '#6b7280'
            }).then((result) => {
                if (result.isConfirmed) {
                    fetch("{% url 'reservar_sesion' %}", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": "{{ csrf_token }}"
                        },
                        body: JSON.stringify({ id_sesion: idSesion })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            Swal.fire({
                                title: '¡Reserva Confirmada!',
                                text: data.message,
                                icon: 'success',
                                confirmButtonColor: 'var(--primary)'
                            }).then(() => {
                                cerrarModalHorarios();
                                window.location.reload();
                            });
                        } else {
                            Swal.fire({
                                title: 'No se pudo reservar',
                                text: data.message,
                                icon: 'warning',
                                confirmButtonColor: 'var(--primary)'
                            });
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire('Error', 'No se pudo procesar la solicitud de reserva.', 'error');
                    });
                }
            });
        }

        // Mueve una reserva a otro horario del mismo profesor: no gasta otra clase del paquete.
        function confirmarReprogramacion(idInscripcion, idSesion, nombreAsignatura, fechaHora) {
            const safeAsig = window.escaparHtml ? window.escaparHtml(nombreAsignatura) : nombreAsignatura;
            const safeFecha = window.escaparHtml ? window.escaparHtml(fechaHora) : fechaHora;
            Swal.fire({
                title: 'Reprogramar clase',
                html: `¿Mover tu reserva de <b>"${safeAsig}"</b> a este horario?<br><br><span style="color:var(--primary); font-weight:600;"><i class="bi bi-clock"></i> ${safeFecha}</span><br><br>No usa otra clase de tu paquete.`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, mover reserva',
                cancelButtonText: 'Volver',
                confirmButtonColor: 'var(--primary)',
                cancelButtonColor: '#6b7280'
            }).then((result) => {
                if (!result.isConfirmed) return;
                fetch("{% url 'reprogramar_inscripcion' 0 %}".replace('/0/', `/${idInscripcion}/`), {
                    method: 'POST',
                    headers: { 'X-CSRFToken': '{{ csrf_token }}' },
                    body: new URLSearchParams({ id_sesion: idSesion })
                })
                .then(res => res.json())
                .then(data => {
                    Swal.fire({
                        title: data.success ? '¡Clase reprogramada!' : 'No se pudo reprogramar',
                        text: data.message,
                        icon: data.success ? 'success' : 'warning',
                        confirmButtonColor: 'var(--primary)'
                    }).then(() => {
                        if (data.success) { cerrarModalHorarios(); window.location.reload(); }
                    });
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire('Error', 'No se pudo procesar la reprogramación.', 'error');
                });
            });
        }
