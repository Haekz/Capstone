{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── GESTIÓN DE MODAL DE HORARIOS Y RESERVAS DE SESIONES ──
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
                        listaEl.innerHTML = data.sesiones.map(s => {
                            const cuposColor = s.cupos_disponibles <= 2 ? '#ef4444' : '#10b981';
const safeIdSesion = Number(s.id_sesion) || 0;
                            const safeAsignatura = escaparHtml(s.asignatura);
                            const safeFecha = escaparHtml(s.fecha_formateada);
                            const safeHora = escaparHtml(s.hora_formateada);
                            const safeModalidad = escaparHtml(s.modalidad).toUpperCase();
                            const safePrecio = escaparHtml(s.precio_formateado);
                            const safeDuracion = Number(s.duracion_minutos) || 0;
                            const safeCupos = Number(s.cupos_disponibles) || 0;

                            const btnHtml = s.ya_inscrito 
                                ? `<button class="ap-btn-enrolled" disabled style="padding: 8px 16px; font-size: 0.85rem;"><i class="bi bi-check-circle-fill"></i> Ya reservado</button>`
                                : idInscripcion
                                ? `<button class="btn-principal btn-mover-sesion" data-id="${safeIdSesion}" data-asig="${safeAsignatura}" data-fechahora="${safeFecha} ${safeHora}" data-inscripcion="${idInscripcion}" style="padding: 8px 16px; font-size: 0.85rem;"><i class="bi bi-calendar2-check ap-mr-4"></i>Mover a este horario</button>`
                                : `<button class="btn-principal btn-reservar-sesion" data-id="${safeIdSesion}" data-asig="${safeAsignatura}" data-fechahora="${safeFecha} ${safeHora}" style="padding: 8px 16px; font-size: 0.85rem;"><i class="bi bi-bookmark-plus-fill ap-mr-4"></i>Reservar este horario</button>`;

                            return `
                                <div class="sesion-item-card" style="border: 1px solid var(--line); background: var(--white); border-radius: 12px; padding: 14px 18px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.03);">
                                    <div style="display: flex; flex-direction: column; gap: 4px;">
                                        <div style="display: flex; align-items: center; gap: 10px;">
                                            <span style="font-weight: 700; font-size: 1.05rem; color: var(--text);">
                                                <i class="bi bi-calendar3" style="color: var(--primary); margin-right: 6px;"></i>${safeFecha}
                                            </span>
                                            <span class="class-status-badge class-status-badge--modality">${safeModalidad}</span>
                                        </div>
                                        <div style="font-size: 0.88rem; color: var(--text-light); display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
                                            <span><i class="bi bi-clock ap-mr-4"></i>${safeHora} (${safeDuracion} min)</span>
                                            <span style="color: ${cuposColor}; font-weight: 600;">
                                                <i class="bi bi-people-fill ap-mr-4"></i>${safeCupos} cupo${safeCupos === 1 ? '' : 's'} disponible${safeCupos === 1 ? '' : 's'}
                                            </span>
                                        </div>
<div style="font-size: 0.9rem; font-weight: 700; color: var(--primary); margin-top: 2px;">
                                            ${idInscripcion ? 'No usa otra clase de tu paquete' : 'Usa 1 clase de tu paquete'}
                                        </div>
                                    </div>
                                    <div style="display: flex; align-items: center; gap: 12px;">
                                        <span style="font-weight: 700; font-size: 1rem; color: var(--text);">${safePrecio}</span>
                                        ${btnHtml}
                                    </div>
                                </div>
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
            Swal.fire({
                title: 'Reprogramar clase',
                html: `¿Mover tu reserva de <b>"${nombreAsignatura}"</b> a este horario?<br><br><span style="color:var(--primary); font-weight:600;"><i class="bi bi-clock"></i> ${fechaHora}</span><br><br>No usa otra clase de tu paquete.`,
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
