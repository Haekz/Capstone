{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── PLAN ACTIVO: lo decide el servidor (paquete vigente o suscripción antigua), no localStorage ──
        const planActivo = JSON.parse(document.getElementById('plan-activo').textContent);
        const hasPlan = planActivo !== null;
        const activePlanName = planActivo ? planActivo.nombre : '';

        const updatePlanUI = () => {
            const planBadge = document.querySelector('.profile-title-box .plan-badge');
            if (planBadge) {
                if (hasPlan) {
                    const safePlan = window.escaparHtml ? window.escaparHtml(activePlanName) : activePlanName;
                    planBadge.innerHTML = `<i class="bi bi-check-circle-fill" style="color: #10b981;"></i> Plan Activo: ${safePlan}`;
                    planBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
                    planBadge.style.color = '#10b981';
                    planBadge.style.borderColor = 'rgba(16, 185, 129, 0.2)';
                } else {
                    planBadge.innerHTML = `<i class="bi bi-x-circle-fill"></i> Sin Plan Activo`;
                    planBadge.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                    planBadge.style.color = '#ef4444';
                    planBadge.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                }
            }
        };
        // ── DATA POOLS ──
        // Teachers: vienen de la vista como JSON (ver profesores_js en views.py).
        // json_script entrega el texto tal cual lo escribio el profesor, asi que
        // todo dato suyo que va a innerHTML pasa por escaparHtml.
        const teachers = JSON.parse(document.getElementById('profesores-data').textContent);
        const escaparHtml = (texto) => String(texto).replace(/[&<>"']/g, (c) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
        // SCRUM-32: enlace al perfil profesional (solo profesores reales; los tutores son de ejemplo).
        const URL_PERFIL_PROFESOR = "{% url 'perfil_profesor' 0 %}";
        const enlacePerfil = (t) =>
            `<a class="teacher-profile-link" href="${URL_PERFIL_PROFESOR.replace(/0\/$/, `${Number(t.id)}/`)}">Ver perfil</a>`;
        // Calificacion real (reseñas visibles). Sin reseñas: "Nuevo", sin estrellas inventadas. Los tutores de ejemplo no traen `rating`.
        const calificacion = (t) => {
            if (!('rating' in t)) return '';
            if (!t.rating) return '<p class="teacher-rating teacher-rating--nuevo">Nuevo</p>';
            const total = Number(t.rating.total);
            const promedio = escaparHtml(t.rating.promedio);
            return `<p class="teacher-rating" aria-label="Calificación ${promedio} de 5, basada en ${total} reseña${total === 1 ? '' : 's'}">` +
                `<i class="bi bi-star-fill" aria-hidden="true"></i> ${promedio} <span>(${total})</span></p>`;
        };
        // Minusculas y sin tildes, para que "matematicas" encuentre "Matemáticas".
        const normalizar = (texto) => String(texto).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

        // Tutors: datos de EJEMPLO (aun no hay tutores reales). La pestana lo avisa.
        const tutors = [
            { id: 101, name: "Tutor Juan Pablo", specialties: ["Matemáticas", "Programación"], initial: "JP" },
            { id: 102, name: "Tutora Camila Gómez", specialties: ["Inglés", "Lenguaje"], initial: "CG" },
            { id: 103, name: "Tutor Roberto Muñoz", specialties: ["Física", "Química"], initial: "RM" },
            { id: 104, name: "Tutora Patricia Soto", specialties: ["Biología"], initial: "PS" }
        ];

