{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── CLASE EXTRA (tramo B) ──
        // Desde la ventana de horarios: si ninguna hora le sirve, el alumno propone otra fuera del horario del profesor.
        // Profesor y materia ya vienen de la ventana. Las reglas las aplica el servidor (alumnos/clase_extra.py): aqui
        // solo se muestran las horas que el devuelve, con el motivo de las que no se pueden pedir.
        const SEMANAS_EXTRA = 4;
        const claseExtra = {};

        function prepararClaseExtra(idClase, asignatura, profesor, puedePedir) {
            Object.assign(claseExtra, {
                clase: idClase, asignatura, profesor, paso: 1, semana: 0, dia: null, horas: null, hora: null,
                cargando: false, enviando: false, error: '', bloqueo: '', mensaje: '', enviado: null,
            });
            document.getElementById('modal-horarios-extra-entrada').hidden = !puedePedir;
            document.getElementById('clase-extra').hidden = true;
            document.querySelector('#modal-horarios-sesiones .custom-modal-body').classList.remove('extra-abierta');
        }

        function abrirClaseExtra() {
            document.querySelector('#modal-horarios-sesiones .custom-modal-body').classList.add('extra-abierta');
            document.getElementById('clase-extra').hidden = false;
            pintarClaseExtra(true);
            // Parte mostrando hoy: si no puede pedir (p. ej. sin paquete con este profesor), lo sabe de inmediato.
            if (!claseExtra.dia && !claseExtra.enviado) elegirDiaExtra(isoExtra(diaExtra(0)));
        }

        function volverAHorarios() {
            document.querySelector('#modal-horarios-sesiones .custom-modal-body').classList.remove('extra-abierta');
            document.getElementById('clase-extra').hidden = true;
            document.querySelector('#modal-horarios-extra-entrada button').focus();
        }

        // Fechas en la hora local del navegador: "AAAA-MM-DD" sin pasar por UTC (toISOString cambiaria el dia de noche).
        const diaExtra = (n) => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + n); return d; };
        const isoExtra = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        const deIsoExtra = (iso) => { const [a, m, d] = iso.split('-').map(Number); return new Date(a, m - 1, d); };
        const fechaLargaExtra = (d) => d.toLocaleDateString('es-CL', {weekday: 'long', day: 'numeric', month: 'long'});

        function elegirDiaExtra(iso) {
            Object.assign(claseExtra, {dia: iso, hora: null, horas: null, cargando: true, error: ''});
            pintarClaseExtra(false);
            const vigente = (data) => claseExtra.dia === iso && data;  // si eligio otro dia mientras cargaba, se ignora
            fetch(`{% url 'clase_extra_horas' %}?clase_id=${encodeURIComponent(claseExtra.clase)}&fecha=${iso}`)
                .then(res => res.json())
                .then(data => {
                    if (!vigente(data)) return;
                    claseExtra.cargando = false;
                    // Si el servidor no da horas, no es por el dia (sin paquete, menor, profesor sin titulo): bloquea.
                    if (data.success) claseExtra.horas = data.horas;
                    else claseExtra.bloqueo = data.message;
                    pintarClaseExtra(false);
                })
                .catch(() => {
                    if (claseExtra.dia !== iso) return;
                    Object.assign(claseExtra, {cargando: false, error: 'No pudimos cargar las horas. Inténtalo de nuevo.'});
                    pintarClaseExtra(false);
                });
        }

        function pasosExtra() {
            return `<ol class="pasos" aria-label="Pasos">${['Día y hora', 'Revisar y enviar'].map((texto, i) => {
                const n = i + 1, hecho = Boolean(claseExtra.enviado) || n < claseExtra.paso;
                const actual = !claseExtra.enviado && n === claseExtra.paso;
                const marca = hecho ? '<i class="bi bi-check-lg" aria-hidden="true"></i><span class="solo-lector">Listo: </span>' : n;
                return `<li class="${hecho ? 'hecho' : ''}"${actual ? ' aria-current="step"' : ''}><span class="num">${marca}</span><span class="txt">${texto}</span></li>`;
            }).join('')}</ol>`;
        }

        function horasExtraHtml() {
            if (!claseExtra.dia) return '<p class="extra-sub">Elige un día para ver las horas.</p>';
            if (claseExtra.cargando) return '<p class="extra-sub" role="status">Buscando horas…</p>';
            if (!claseExtra.horas) return '';
            const botones = claseExtra.horas.map((h, i) => {
                const hora = escaparHtml(h.hora), motivo = escaparHtml(h.motivo);
                const apagada = h.motivo ? ` disabled title="${motivo}" aria-label="${hora}, no se puede pedir: ${motivo}"` : '';
                return `<button type="button" class="tira-hora" data-extra-hora="${i}" aria-pressed="${claseExtra.hora === i}"${apagada}>${hora}</button>`;
            }).join('');
            const ninguna = claseExtra.horas.some(h => !h.motivo) ? '' : '<p class="extra-sub">Ese día no hay horas para pedir. Prueba otro día.</p>';
            return `${ninguna}<div class="tira-horas" role="group" aria-labelledby="extra-rotulo-hora">${botones}</div>
                <div class="leyenda"><span class="libre">Se puede pedir</span><span>No se puede pedir</span></div>`;
        }

        function pasoDiaYHora() {
            const chips = Array.from({length: 7}, (_, i) => diaExtra(claseExtra.semana * 7 + i)).map(d => {
                const iso = isoExtra(d), corto = d.toLocaleDateString('es-CL', {weekday: 'short'}).replace('.', '');
                return `<button type="button" class="tira-dia" data-extra-dia="${iso}" aria-pressed="${claseExtra.dia === iso}" aria-label="${escaparHtml(fechaLargaExtra(d))}"><span>${escaparHtml(corto)}</span><strong>${d.getDate()}</strong></button>`;
            }).join('');
            return `<h4 tabindex="-1" id="clase-extra-titulo" class="extra-titulo">Pide una clase extra: ¿qué día y a qué hora?</h4>
                <p class="extra-sub">Propón una hora fuera del horario de ${escaparHtml(claseExtra.profesor)}: si la acepta, queda reservada. Cada clase dura 60 minutos. Horas de Chile.</p>
                <div class="bloque"><span class="rotulo" id="extra-rotulo-dia">Día</span>
                    <div class="semana">
                        <button type="button" class="flecha" data-extra-semana="-1" aria-label="Semana anterior"${claseExtra.semana === 0 ? ' disabled' : ''}><i class="bi bi-chevron-left" aria-hidden="true"></i></button>
                        <div class="tira-dias" role="group" aria-labelledby="extra-rotulo-dia">${chips}</div>
                        <button type="button" class="flecha" data-extra-semana="1" aria-label="Semana siguiente"${claseExtra.semana >= SEMANAS_EXTRA - 1 ? ' disabled' : ''}><i class="bi bi-chevron-right" aria-hidden="true"></i></button>
                    </div></div>
                <div class="bloque"><span class="rotulo" id="extra-rotulo-hora">Hora</span>${horasExtraHtml()}</div>
                <div class="aviso"><i class="bi bi-info-circle" aria-hidden="true"></i><span>Las horas apagadas no se pueden pedir: están dentro del horario normal del profesor (esas se reservan en la lista de horarios), ya tiene otra clase, faltan menos de 4 horas o tu paquete vence antes.</span></div>`;
        }

        function pasoRevisar() {
            const h = claseExtra.horas[claseExtra.hora];
            const cuando = `${fechaLargaExtra(deIsoExtra(claseExtra.dia))}, ${h.hora}`;
            return `<h4 tabindex="-1" id="clase-extra-titulo" class="extra-titulo">Revisa tu pedido</h4>
                <p class="extra-sub">Todavía no es una clase: es un pedido que el profesor tiene que aceptar.</p>
                <dl class="resumen">
                    <div><dt>Profesor</dt><dd>${escaparHtml(claseExtra.profesor)}</dd></div>
                    <div><dt>Materia</dt><dd>${escaparHtml(claseExtra.asignatura)}</dd></div>
                    <div><dt>Día y hora</dt><dd>${escaparHtml(cuando)}</dd></div>
                    <div><dt>Duración</dt><dd>60 minutos</dd></div>
                    <div><dt>Cómo se paga</dt><dd>1 clase de tu paquete, solo si acepta</dd></div>
                </dl>
                <div class="bloque"><label class="rotulo" for="clase-extra-mensaje">Mensaje para el profesor <span class="opcional">(opcional)</span></label>
                    <textarea id="clase-extra-mensaje" maxlength="500" placeholder="Por ejemplo: tengo prueba el viernes y necesito repasar fracciones.">${escaparHtml(claseExtra.mensaje)}</textarea>
                    <div class="contador" id="clase-extra-contador">${claseExtra.mensaje.length} / 500</div></div>
                <div class="aviso"><i class="bi bi-hourglass-split" aria-hidden="true"></i><span>El profesor tiene <b>24 horas</b> para responder (o hasta 4 horas antes de la clase, si eso llega antes). Si acepta, la clase queda reservada y se descuenta una clase de tu paquete. Si rechaza o no responde, <b>no se descuenta nada</b>.</span></div>`;
        }

        function pasoBloqueado() {
            return `<h4 tabindex="-1" id="clase-extra-titulo" class="extra-titulo">Pide una clase extra</h4>
                <p class="extra-error extra-bloqueo" role="alert"><i class="bi bi-exclamation-circle" aria-hidden="true"></i> ${escaparHtml(claseExtra.bloqueo)}</p>
                <div class="acciones"><button type="button" class="btn-secundario" data-extra-accion="atras">Volver a los horarios</button></div>`;
        }

        function pasoEnviado() {
            return `<div class="exito"><i class="bi bi-send-check gran" aria-hidden="true"></i>
                    <h4 tabindex="-1" id="clase-extra-titulo" class="extra-titulo">¡Pedido enviado!</h4>
                    <p>${escaparHtml(claseExtra.enviado)}</p></div>
                <div class="aviso"><i class="bi bi-info-circle" aria-hidden="true"></i><span>Te avisaremos por correo y en la campanita apenas responda. Mientras tanto no se descuenta ninguna clase y puedes seguir reservando. Eso sí: <b>si cuando acepte ya no te quedan clases en el paquete, el pedido vence</b>.</span></div>
                <div class="acciones"><span></span><button type="button" class="btn-principal" onclick="cerrarModalHorarios()">Listo</button></div>`;
        }

        // conFoco: lleva el foco al titulo del paso. Si no, el foco vuelve al mismo boton que lo tenia (al redibujar se
        // reemplaza el html: sin esto, quien usa teclado perderia su lugar, tambien cuando las horas llegan despues).
        function pintarClaseExtra(conFoco) {
            const seccion = document.getElementById('clase-extra');
            const activo = seccion.contains(document.activeElement) ? document.activeElement : null;
            const clave = activo && ['extraDia', 'extraHora', 'extraSemana', 'extraAccion'].find(k => activo.dataset[k] !== undefined);
            const selector = clave && `[data-${clave.replace(/[A-Z]/g, c => '-' + c.toLowerCase())}="${activo.dataset[clave]}"]`;

            if (claseExtra.bloqueo) {
                seccion.innerHTML = pasoBloqueado();
            } else {
                const cuerpo = claseExtra.enviado ? pasoEnviado() : claseExtra.paso === 1 ? pasoDiaYHora() : pasoRevisar();
                const error = claseExtra.error ? `<p class="extra-error" role="alert"><i class="bi bi-exclamation-circle" aria-hidden="true"></i> ${escaparHtml(claseExtra.error)}</p>` : '';
                const seguir = claseExtra.paso === 1 ? 'Continuar' : claseExtra.enviando ? 'Enviando…' : 'Enviar pedido';
                const acciones = claseExtra.enviado ? '' : `<div class="acciones">
                    <button type="button" class="btn-secundario" data-extra-accion="atras">${claseExtra.paso === 1 ? 'Volver a los horarios' : 'Atrás'}</button>
                    <button type="button" class="btn-principal" data-extra-accion="seguir"${claseExtra.enviando ? ' disabled' : ''}>${seguir}</button></div>`;
                seccion.innerHTML = pasosExtra() + cuerpo + error + acciones;
            }

            const titulo = document.getElementById('clase-extra-titulo');
            const mismo = selector && seccion.querySelector(selector);
            if (conFoco) titulo.focus();
            else if (activo) (mismo && !mismo.disabled ? mismo : titulo).focus();
        }

        function seguirClaseExtra() {
            claseExtra.error = '';
            if (claseExtra.paso === 2) return enviarClaseExtra();
            if (!claseExtra.dia) claseExtra.error = 'Elige un día para continuar.';
            else if (claseExtra.hora === null) claseExtra.error = 'Elige una hora para continuar.';
            if (claseExtra.error) return pintarClaseExtra(false);
            claseExtra.paso = 2;
            pintarClaseExtra(true);
        }

        function enviarClaseExtra() {
            claseExtra.enviando = true;
            pintarClaseExtra(false);
            fetch("{% url 'clase_extra_pedir' %}", {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}'},
                body: JSON.stringify({
                    clase_id: claseExtra.clase, inicio: claseExtra.horas[claseExtra.hora].inicio, mensaje: claseExtra.mensaje,
                }),
            })
                .then(res => res.json())
                .then(data => {
                    claseExtra.enviando = false;
                    if (data.success) claseExtra.enviado = data.message;
                    else claseExtra.error = data.message;
                    pintarClaseExtra(Boolean(data.success));
                })
                .catch(() => {
                    Object.assign(claseExtra, {enviando: false, error: 'No pudimos enviar tu pedido. Inténtalo de nuevo.'});
                    pintarClaseExtra(false);
                });
        }

        const seccionClaseExtra = document.getElementById('clase-extra');
        if (seccionClaseExtra) {
            seccionClaseExtra.addEventListener('click', (ev) => {
                const b = ev.target.closest('button');
                if (!b || b.disabled) return;
                const d = b.dataset;
                if (d.extraDia) return elegirDiaExtra(d.extraDia);
                if (d.extraHora !== undefined) { Object.assign(claseExtra, {hora: Number(d.extraHora), error: ''}); return pintarClaseExtra(false); }
                if (d.extraSemana) { claseExtra.semana += Number(d.extraSemana); return pintarClaseExtra(false); }
                if (d.extraAccion === 'seguir') return seguirClaseExtra();
                if (d.extraAccion !== 'atras') return;
                if (claseExtra.paso === 1 || claseExtra.bloqueo) return volverAHorarios();
                const habiaError = Boolean(claseExtra.error);  // p. ej. alguien tomo esa hora: se vuelven a pedir las horas
                Object.assign(claseExtra, {paso: 1, error: ''});
                if (habiaError) elegirDiaExtra(claseExtra.dia);
                pintarClaseExtra(true);
            });
            seccionClaseExtra.addEventListener('input', (ev) => {
                if (ev.target.id !== 'clase-extra-mensaje') return;
                claseExtra.mensaje = ev.target.value;
                document.getElementById('clase-extra-contador').textContent = `${claseExtra.mensaje.length} / 500`;
            });
        }
