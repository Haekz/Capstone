/* Portal del apoderado: ayudas de formularios, dialogo de mensajes y bienvenida de planes.
   Viene del bloque 5 de la copia del apoderado. Solo usa lo que el servidor ya pinto (sin llamadas nuevas) y cada parte
   revisa que su elemento exista. Todo es ayuda en el navegador: el servidor sigue validando todo. */
(() => {
    'use strict';
    const $ = (sel, raiz = document) => raiz.querySelector(sel);
    const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

    /* ── 5. Mensajes: el "?" abre la ventana; se cierra con Esc, la X, "Entendido" o haciendo clic fuera ── */
    $$('.btn-ayuda-mensajes').forEach(b => {
        const dlg = document.getElementById(b.getAttribute('aria-controls'));
        if (!dlg || !dlg.showModal) return;
        b.addEventListener('click', () => dlg.showModal());
        dlg.addEventListener('click', ev => { if (ev.target === dlg) dlg.close(); });
    });

    /* ── 6. Registrar y vincular: RUT, contraseña, documento y campos obligatorios ── */
    const MENSAJES = {
        nombre: 'Escribe el nombre completo del estudiante.',
        rut: 'Escribe el RUT del estudiante.',
        fecha_nacimiento: 'Indica su fecha de nacimiento.',
        password: 'Crea una contraseña para el estudiante.',
        confirmar_password: 'Repite la contraseña.',
        documento: 'Adjunta el documento que acredita tu vínculo.',
        acepta_declaracion: 'Marca la declaración para continuar.'
    };
    const MAX_MB = 5;
    const hoyISO = (() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; })();

    // RUT chileno: cuerpo + dígito verificador (módulo 11)
    const limpiarRut = v => (v || '').replace(/[^0-9kK]/g, '').toUpperCase();
    const formatearRut = v => {
        const r = limpiarRut(v);
        if (r.length < 2) return v;
        const cuerpo = r.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
        return `${cuerpo}-${r.slice(-1)}`;
    };
    const rutValido = v => {
        const r = limpiarRut(v);
        if (r.length < 2 || !/^\d+$/.test(r.slice(0, -1))) return false;
        let suma = 0, mult = 2;
        for (let i = r.length - 2; i >= 0; i--) { suma += Number(r[i]) * mult; mult = mult === 7 ? 2 : mult + 1; }
        const dv = 11 - (suma % 11);
        return r.slice(-1) === (dv === 11 ? '0' : dv === 10 ? 'K' : String(dv));
    };

    const contenedor = campo => campo.closest('.apod-form__campo, .apod-form__declaracion') || campo.parentElement;
    function quitarError(campo) {
        campo.removeAttribute('aria-invalid');
        const e = document.getElementById(campo.id + '-error');
        if (e) e.remove();
    }
    function ponerError(campo, texto) {
        quitarError(campo);
        const p = document.createElement('p');
        p.className = 'apo-error';
        p.id = campo.id + '-error';
        const icono = document.createElement('i');
        icono.className = 'bi bi-exclamation-circle-fill';
        icono.setAttribute('aria-hidden', 'true');
        p.append(icono, ' ' + texto);
        contenedor(campo).append(p);
        campo.setAttribute('aria-invalid', 'true');
        const desc = (campo.getAttribute('aria-describedby') || '').split(' ').filter(x => x && x !== p.id);
        campo.setAttribute('aria-describedby', [...desc, p.id].join(' '));
    }

    $$('form.apo-form').forEach(form => {
        const boton = $('button[type="submit"]', form);
        const rut = $('input[name="rut"]', form);
        const fecha = $('input[name="fecha_nacimiento"]', form);
        const p1 = $('input[name="password"]', form);
        const p2 = $('input[name="confirmar_password"]', form);
        const archivo = $('input[type="file"]', form);

        if (fecha) fecha.max = hoyISO;

        if (rut) rut.addEventListener('blur', () => {
            if (rut.value.trim()) rut.value = formatearRut(rut.value);
            if (rut.value.trim() && !rutValido(rut.value)) ponerError(rut, 'Revisa el RUT: el dígito verificador no coincide.');
        });

        // Reglas de la contraseña en vivo, igual que en "Cambiar contraseña"
        let reglas = null;
        if (p1 && p2) {
            reglas = document.createElement('ul');
            reglas.className = 'apo-reglas';
            reglas.setAttribute('aria-live', 'polite');
            reglas.innerHTML = [['largo', 'Al menos 8 caracteres'], ['numeros', 'No puede ser solo números'], ['iguales', 'Ambas contraseñas coinciden']]
                .map(([k, t]) => `<li data-regla="${k}"><i class="bi bi-circle" aria-hidden="true"></i> ${t}</li>`).join('');
            contenedor(p2).after(reglas);
            const revisar = () => {
                const a = p1.value, b = p2.value;
                const estado = { largo: a.length >= 8, numeros: a.length > 0 && !/^\d+$/.test(a), iguales: a.length > 0 && a === b };
                $$('li', reglas).forEach(li => {
                    const ok = estado[li.dataset.regla];
                    li.classList.toggle('ok', ok);
                    $('i', li).className = ok ? 'bi bi-check-circle-fill' : 'bi bi-circle';
                });
            };
            [p1, p2].forEach(el => el.addEventListener('input', revisar));
        }

        // Documento: nombre y peso a la vista; avisa si es muy grande o de otro tipo
        if (archivo) archivo.addEventListener('change', () => {
            quitarError(archivo);
            const ya = $('.apo-archivo', contenedor(archivo));
            if (ya) ya.remove();
            const f = archivo.files && archivo.files[0];
            if (!f) return;
            const mb = f.size / 1048576;
            const tipos = (archivo.accept || '').split(',').map(t => t.trim()).filter(Boolean);
            if (tipos.length && f.type && !tipos.includes(f.type)) { ponerError(archivo, 'El documento tiene que ser JPG, PNG o PDF.'); return; }
            if (mb > MAX_MB) { ponerError(archivo, `El archivo pesa ${mb.toFixed(1).replace('.', ',')} MB; el máximo es ${MAX_MB} MB.`); return; }
            const info = document.createElement('p');
            info.className = 'apo-archivo';
            info.innerHTML = '<i class="bi bi-file-earmark-check-fill" aria-hidden="true"></i> ';
            info.append(`${f.name} · ${mb < 1 ? Math.max(1, Math.round(f.size / 1024)) + ' KB' : mb.toFixed(1).replace('.', ',') + ' MB'}`);
            archivo.after(info);
        });

        $$('input:not([type="file"]), select, textarea', form).forEach(c => {  // el documento tiene su propia revisión
            const limpiar = () => { if (c.type === 'checkbox' ? c.checked : c.value.trim()) quitarError(c); };
            c.addEventListener('input', limpiar);
            c.addEventListener('change', limpiar);
        });

        form.addEventListener('submit', ev => {
            const malos = [];
            $$('input[required], select[required], textarea[required]', form).forEach(c => {
                quitarError(c);
                const vacio = c.type === 'checkbox' ? !c.checked : c.type === 'file' ? !(c.files && c.files.length) : !c.value.trim();
                if (vacio) { ponerError(c, MENSAJES[c.name] || 'Completa este campo.'); malos.push(c); }
            });
            if (rut && rut.value.trim() && !rutValido(rut.value)) { ponerError(rut, 'Revisa el RUT: el dígito verificador no coincide.'); malos.push(rut); }
            if (fecha && fecha.value && fecha.value > hoyISO) { ponerError(fecha, 'La fecha no puede ser posterior a hoy.'); malos.push(fecha); }
            if (p1 && p2 && p2.value && p1.value !== p2.value) { ponerError(p2, 'Las contraseñas no coinciden.'); malos.push(p2); }
            if (archivo && archivo.files && archivo.files[0] && archivo.files[0].size > MAX_MB * 1048576) { ponerError(archivo, `El máximo es ${MAX_MB} MB.`); malos.push(archivo); }
            if (malos.length) {
                ev.preventDefault();
                const primero = form.querySelector('[aria-invalid="true"]');
                if (primero) primero.focus();
                return;
            }
            if (boton) {
                if (boton.disabled) { ev.preventDefault(); return; }
                boton.disabled = true;
                boton.dataset.texto = boton.innerHTML;
                boton.innerHTML = '<i class="bi bi-hourglass-split" aria-hidden="true"></i> Enviando…';
            }
        });
        window.addEventListener('pageshow', () => {
            if (boton && boton.dataset.texto) { boton.disabled = false; boton.innerHTML = boton.dataset.texto; }
        });
    });

    /* ── 7. Planes: la bienvenida se muestra solo la primera vez ── */
    const bienvenida = $('#welcome-modal');
    if (bienvenida) {
        let vista = false;
        try { vista = localStorage.getItem('apo-planes-bienvenida') === '1'; } catch (e) { /* sin almacenamiento */ }
        const cerrar = () => {
            bienvenida.classList.remove('apo-modal--visible');
            try { localStorage.setItem('apo-planes-bienvenida', '1'); } catch (e) { /* sin almacenamiento */ }
        };
        if (!vista) bienvenida.classList.add('apo-modal--visible');
        const ok = $('#close-modal-btn');
        if (ok) ok.addEventListener('click', cerrar);
        bienvenida.addEventListener('click', ev => { if (ev.target === bienvenida) cerrar(); });
        document.addEventListener('keydown', ev => {
            if (ev.key === 'Escape' && bienvenida.classList.contains('apo-modal--visible')) cerrar();
        });
    }
})();
