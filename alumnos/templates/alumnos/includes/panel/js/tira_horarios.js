{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── TIRA DE HORARIOS EN LA TARJETA DEL PROFESOR ──
        // t.horarios: [{id_sesion, asignatura, fecha 'AAAA-MM-DD', hora 'HH:MM'}] de los proximos 7 dias
        // (los arma alumnos/horarios_profesores.py). Reservar reutiliza confirmarReservaSesion (horarios.js).
        const DIAS_DE_LA_TIRA = 7;
        // Hoy en Chile, igual que las fechas del servidor. Los dias se suman en UTC: el cambio de hora no los corre.
        const hoyEnChile = () => new Date().toLocaleDateString('en-CA', {timeZone: 'America/Santiago'});
        const fechaUtc = (iso) => { const [a, m, d] = iso.split('-').map(Number); return new Date(Date.UTC(a, m - 1, d)); };
        const sumarDias = (iso, n) => { const f = fechaUtc(iso); f.setUTCDate(f.getUTCDate() + n); return f.toISOString().slice(0, 10); };
        const fechaDdMmAaaa = (iso) => iso.split('-').reverse().join('/');
        const textoDeFecha = (iso, opciones) => fechaUtc(iso).toLocaleDateString('es-CL', {...opciones, timeZone: 'UTC'}).replace('.', '');

        const horasDelDia = (t, dia) => t.horarios.filter(h => h.fecha === dia);
        const htmlHoras = (t, dia) => horasDelDia(t, dia).map(h =>
            `<button type="button" class="tira-hora" data-sesion="${Number(h.id_sesion)}" data-asig="${escaparHtml(h.asignatura)}" ` +
            `data-fechahora="${escaparHtml(`${fechaDdMmAaaa(h.fecha)} ${h.hora}`)}">${escaparHtml(h.hora)}</button>`
        ).join('');

        function tiraHorarios(t) {
            const dias = Array.from({length: DIAS_DE_LA_TIRA}, (_, i) => sumarDias(hoyEnChile(), i));
            const elegido = dias.find(dia => horasDelDia(t, dia).length);
            if (!elegido) {
                return `<p class="tira-vacia">Sin horarios disponibles en los próximos ${DIAS_DE_LA_TIRA} días</p>`;
            }
            const botones = dias.map(dia => {
                const cantidad = horasDelDia(t, dia).length;
                const nombre = textoDeFecha(dia, {weekday: 'long', day: 'numeric', month: 'long'});
                const aviso = cantidad ? `${cantidad} horario${cantidad === 1 ? '' : 's'}` : 'sin horarios';
                return `<button type="button" class="tira-dia" data-dia="${dia}" aria-pressed="${dia === elegido}" ` +
                    `aria-label="${escaparHtml(`${nombre}, ${aviso}`)}"${cantidad ? '' : ' disabled'}>` +
                    `<span>${escaparHtml(textoDeFecha(dia, {weekday: 'short'}))}</span><strong>${Number(dia.slice(8))}</strong></button>`;
            }).join('');
            return `<div class="tira-horarios" data-profesor="${Number(t.id)}">` +
                `<div class="tira-dias" role="group" aria-label="Días con horarios de ${escaparHtml(t.name)}">${botones}</div>` +
                `<div class="tira-horas" aria-live="polite">${htmlHoras(t, elegido)}</div></div>`;
        }

        // En pantallas angostas la tira se desliza: deja a la vista el dia elegido (donde estan las horas). Va con la
        // tarjeta ya puesta en la pagina, porque necesita medir.
        function mostrarDiaElegido(tarjeta) {
            const tira = tarjeta.querySelector('.tira-dias');
            const elegido = tira && tira.querySelector('.tira-dia[aria-pressed="true"]');
            if (!elegido) return;
            const desfase = elegido.getBoundingClientRect().left - tira.getBoundingClientRect().left;
            tira.scrollLeft += desfase - (tira.clientWidth - elegido.offsetWidth) / 2;
        }

        // Un solo oyente para todas las tarjetas (se vuelven a dibujar al filtrar o buscar).
        document.addEventListener('click', (e) => {
            const dia = e.target.closest('.tira-dia');
            if (dia) {
                const tira = dia.closest('.tira-horarios');
                const t = teachers.find(p => p.id === Number(tira.dataset.profesor));
                tira.querySelectorAll('.tira-dia').forEach(b => b.setAttribute('aria-pressed', String(b === dia)));
                tira.querySelector('.tira-horas').innerHTML = htmlHoras(t, dia.dataset.dia);
                return;
            }
            const hora = e.target.closest('.tira-hora');
            if (hora) confirmarReservaSesion(hora.dataset.sesion, hora.dataset.asig, hora.dataset.fechahora);
        });
