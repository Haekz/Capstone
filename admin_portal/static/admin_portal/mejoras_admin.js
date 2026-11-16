/* Portal de admin: mejoras de uso (de la copia: bloque 5). Solo usa lo que el servidor ya pintó; cada parte revisa que su elemento exista.
   Va al final de base_admin.html, despues del script de cada pagina (el del dashboard define `titles` y `showSection`).

   Lo que NO se porto tal cual de la copia, porque alli las 10 secciones viven en una sola pagina y aqui no:
   - El banner del Resumen (fecha y pendientes): lo arma el servidor (admin_portal/metricas.py: pendientes). La copia contaba reseñas y
     casos escalados leyendo las secciones Reseñas y Escalados, que aqui son paginas aparte: habria mostrado siempre cero.
   - El buscador Ctrl+K con las secciones: la lista completa ya viene en base_admin.html (la copia la armaba con el mapa `titles`,
     que aqui solo tiene las 5 secciones del dashboard). */
(function () {
    const $ = (sel, raiz = document) => raiz.querySelector(sel);
    const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));
    const numero = (t) => { const n = parseInt(String(t).replace(/[^\d]/g, ''), 10); return Number.isNaN(n) ? 0 : n; };
    const sinTildes = (t) => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

    // ── 1. Esc también cierra el panel de notificaciones (todas las páginas del portal) ──
    document.addEventListener('keydown', (e) => {
        if (e.key !== 'Escape') return;
        const cajon = $('#notifications-drawer');
        if (cajon && cajon.classList.contains('active')) cajon.classList.remove('active');
    });

    if (!document.getElementById('section-resumen')) return;  // lo que sigue es del dashboard

    // ── 2. Al cambiar de sección: título de la pestaña, menú marcado y volver arriba ──
    function alCambiar() {
        const nombre = (window.location.hash.replace('#', '') || 'resumen');
        const t = titles[nombre] || titles.resumen;
        document.title = `${t[0]} | LBWUS Admin`;
        $$('.sidebar .nav-item[id^="nav-"]').forEach(a => {
            if (a.id === 'nav-' + (titles[nombre] ? nombre : 'resumen')) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
        });
        window.scrollTo(0, 0);
    }
    window.addEventListener('hashchange', alCambiar);
    window.addEventListener('DOMContentLoaded', alCambiar);

    // ── 3. Indicadores del Resumen: llevan a su sección ──
    $$('#section-resumen .stat-card[data-ir]').forEach(card => {
        card.setAttribute('role', 'link');
        card.setAttribute('tabindex', '0');
        const ir = () => { window.location.hash = card.dataset.ir; };
        card.addEventListener('click', ir);
        card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ir(); } });
    });

    // ── 4. Soporte en cifras: si todo está en cero, la tabla de 12 filas queda plegada ──
    const tablaSoporte = $('.soporte-tabla');
    if (tablaSoporte) {
        const celdas = $$('tbody td', tablaSoporte);
        if (celdas.length && celdas.every(td => numero(td.textContent) === 0)) {
            const det = document.createElement('details');
            det.className = 'soporte-detalle';
            det.innerHTML = '<summary>Sin tickets en ninguna categoría. Ver el detalle</summary>';
            tablaSoporte.before(det);
            det.appendChild(tablaSoporte);
        }
    }

    // ── 5. Usuarios: aviso cuando la búsqueda no encuentra a nadie, y búsqueda que tampoco distingue tildes ──
    const buscador = $('#user-search');
    if (buscador) {
        const sinResultados = document.createElement('p');
        sinResultados.className = 'adm-sin-resultados';
        sinResultados.hidden = true;
        $('.users-toolbar')?.after(sinResultados);
        const revisar = () => {
            const tabla = $$('[id^="users-"]').find(d => d.style.display !== 'none');
            const visibles = tabla ? $$('.user-row', tabla).filter(r => r.style.display !== 'none').length : 0;
            const q = buscador.value.trim();
            sinResultados.hidden = !q || visibles > 0;
            sinResultados.textContent = `Nadie calza con "${q}". Busca por nombre, RUT o correo.`;
        };
        buscador.addEventListener('input', revisar);
        const tabOriginal = window.showUserTab;
        window.showUserTab = (tab) => { tabOriginal(tab); window.filterUsers(); revisar(); };
        // La búsqueda no distinguía mayúsculas solo en el texto escrito: ahora tampoco tildes
        window.filterUsers = () => {
            const q = sinTildes(buscador.value);
            const tabla = $$('[id^="users-"]').find(d => d.style.display !== 'none');
            if (!tabla) return;
            $$('.user-row', tabla).forEach(row => {
                const texto = sinTildes(`${row.dataset.name} ${row.dataset.rut} ${row.dataset.correo}`);
                row.style.display = texto.includes(q) ? '' : 'none';
            });
        };
    }

    // ── 6. Eliminar: ventana propia con el nombre (antes el confirm() del navegador, que queda de respaldo) ──
    window.confirmarEliminar = (form, e) => {
        if (!window.Swal || form.dataset.confirmado) return form.dataset.confirmado ? true : confirm(`¿Seguro que quieres eliminar a ${form.dataset.confirmar}?`);
        e.preventDefault();
        Swal.fire({
            title: `¿Eliminar a ${form.dataset.confirmar}?`,
            text: 'Esta acción no se puede deshacer.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: 'Eliminar',
            cancelButtonText: 'Cancelar',
            customClass: {confirmButton: 'swal-peligro'},
            focusCancel: true,
        }).then(r => {
            if (!r.isConfirmed) return;
            form.dataset.confirmado = '1';
            form.submit();
        });
        return false;
    };
})();
