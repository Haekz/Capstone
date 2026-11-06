{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── MULTI-VIEW ROUTING (Dashboard, Favorites, Profile, Classes, Support, Premium Views) ──
        // esta parte es del enrutamiento de las diferentes vistas de la app
        const viewBtns = document.querySelectorAll('.nav-view-btn, .sidebar-view-btn');
        const views = document.querySelectorAll('.dashboard-view');

        const switchView = (targetViewId) => {
            // Remove active state from all buttons and views
            viewBtns.forEach(btn => {
                const viewAttr = btn.getAttribute('data-view');
                if (viewAttr === targetViewId) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            });

            views.forEach(view => {
                if (view.id === targetViewId) {
                    view.classList.add('active');
                } else {
                    view.classList.remove('active');
                }
            });

            // Control de vistas Premium
            const isPremium = hasPlan && planActivo.premium;
            
            const checkPremiumView = (viewId, lockId, contentId, renderFn) => {
                if (targetViewId === viewId) {
                    const lockEl = document.getElementById(lockId);
                    const contentEl = document.getElementById(contentId);
                    if (isPremium) {
                        if (lockEl) lockEl.style.display = 'none';
                        if (contentEl) contentEl.style.display = 'block';
                        if (renderFn) renderFn();
                    } else {
                        if (lockEl) lockEl.style.display = 'flex';
                        if (contentEl) contentEl.style.display = 'none';
                    }
                }
            };

            checkPremiumView('view-inbox', 'lock-inbox', 'inbox-unlocked-content');
            checkPremiumView('view-progress', 'lock-progress', 'progress-unlocked-content');

            if (targetViewId === 'view-favorites') {
                renderFavorites();
            } else if (targetViewId === 'view-my-classes') {
                renderMyClasses();
            } else if (targetViewId === 'view-support') {
                renderMyReports();
            }
        };

        viewBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetViewId = btn.getAttribute('data-view');
                switchView(targetViewId);
                if (window.innerWidth <= 900) closeSidebar();
            });
        });

        // ── INTERACTIVE MODAL CONTROLLER ──
        const modalOverlay = document.getElementById('interests-modal');
        const openModalBtn = document.getElementById('nav-open-interests');
        const setupBtn = document.getElementById('dashboard-setup-btn');
        const closeModalBtn = document.getElementById('close-modal-btn');
        const acceptModalBtn = document.getElementById('modal-accept-btn');

        const openModal = () => {
            modalOverlay.classList.add('open');
            renderModalPreview();
        };

        const closeModal = () => {
            modalOverlay.classList.remove('open');
        };

        const applyFiltersAndClose = () => {
            const selectedTopics = getSelectedTopics();
            localStorage.setItem('selected-topics', JSON.stringify(selectedTopics));
            renderDashboardContent();
            closeModal();
        };

        if (openModalBtn) openModalBtn.addEventListener('click', openModal);
        if (setupBtn) setupBtn.addEventListener('click', openModal);
        if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
        if (acceptModalBtn) acceptModalBtn.addEventListener('click', applyFiltersAndClose);
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) closeModal();
            });
        }

        // First Login Auto-Open
        const firstLoginDone = localStorage.getItem('first_login_done');
        if (!firstLoginDone) {
            setTimeout(() => {
                openModal();
                localStorage.setItem('first_login_done', 'true');
            }, 800);
        }

        // ── FAVORITES SYSTEM ──
        let favoriteIds = JSON.parse(localStorage.getItem('favorite-teachers') || '[]');

        const toggleFavorite = (teacherId, event) => {
            event.stopPropagation(); // Evita clics no deseados en la tarjeta
            
            const index = favoriteIds.indexOf(teacherId);
            if (index === -1) {
                favoriteIds.push(teacherId);
            } else {
                favoriteIds.splice(index, 1);
            }
            
            localStorage.setItem('favorite-teachers', JSON.stringify(favoriteIds));
            
            // Re-render
            renderDashboardContent();
            renderModalPreview();
            renderFavorites();
        };

        const isFavorite = (teacherId) => favoriteIds.includes(teacherId);
