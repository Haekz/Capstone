{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── RENDERING METHODS ──

        // Modal Preview list
        function renderModalPreview() {
            const selectedTopics = getSelectedTopics();
            const container = document.getElementById('teachers-list-container');
            const countBadge = document.getElementById('teachers-count');
            if (!container) return;
            container.innerHTML = '';

            let filtered = teachers;
            if (selectedTopics.length > 0) {
                filtered = teachers.filter(t => 
                    t.specialties.some(spec => selectedTopics.includes(spec))
                );
            }

            if (countBadge) countBadge.innerText = `${filtered.length} encontrados`;

            if (filtered.length === 0) {
                container.innerHTML = `
                    <div class="empty-teachers-state">
                        <i class="bi bi-person-fill-exclamation"></i>
                        <p>Elige temas de interés arriba.</p>
                    </div>
                `;
                return;
            }

            filtered.forEach(t => {
                const favClass = isFavorite(t.id) ? 'bi-star-fill' : 'bi-star';
                const card = document.createElement('div');
                card.className = 'teacher-card';
                card.innerHTML = `
                    <button type="button" class="teacher-star-btn" aria-label="Marcar profesor como favorito" onclick="toggleFavorite(${t.id}, event)">
                        <i class="${favClass}"></i>
                    </button>
                    <div class="teacher-avatar">${escaparHtml(t.initial)}</div>
                    <div class="teacher-info">
                        <h4>${escaparHtml(t.name)}</h4>
                        <p class="teacher-specialty">${escaparHtml(t.specialties.join(', '))}</p>
                        ${calificacion(t)}
                        ${enlacePerfil(t)}
                    </div>
                `;
                container.appendChild(card);
            });
        }

        // Dashboard Content Tabs (supports search query)
        function renderDashboardContent() {
            const selectedTopics = getSelectedTopics();
            const searchInput = document.getElementById('dashboard-search-input');
            const searchQuery = searchInput ? normalizar(searchInput.value.trim()) : '';
            
            // 1. Teachers
            const teachersContainer = document.getElementById('dashboard-teachers-container');
            if (teachersContainer) {
                teachersContainer.innerHTML = '';
                let filteredTeachers = teachers;
                if (selectedTopics.length > 0) {
                    filteredTeachers = filteredTeachers.filter(t => 
                        t.specialties.some(spec => selectedTopics.includes(spec))
                    );
                }
                if (searchQuery) {
                    filteredTeachers = filteredTeachers.filter(t => 
                        normalizar(t.name).includes(searchQuery) ||
                        t.specialties.some(spec => normalizar(spec).includes(searchQuery))
                    );
                }
                
                if (filteredTeachers.length === 0) {
                    teachersContainer.innerHTML = `<div class="empty-teachers-state"><i class="bi bi-person-fill-exclamation"></i><p>No hay profesores que coincidan con tu búsqueda.</p></div>`;
                } else {
                    filteredTeachers.forEach(t => {
                        const favClass = isFavorite(t.id) ? 'bi-star-fill' : 'bi-star';
                        const card = document.createElement('div');
                        card.className = 'teacher-card';
                        card.innerHTML = `
                            <button type="button" class="teacher-star-btn" aria-label="Marcar profesor como favorito" onclick="toggleFavorite(${t.id}, event)">
                                <i class="${favClass}"></i>
                            </button>
                            <div class="teacher-avatar">${escaparHtml(t.initial)}</div>
                            <div class="teacher-info">
                                <h4>${escaparHtml(t.name)}</h4>
                                <p class="teacher-specialty">${escaparHtml(t.specialties.join(', '))}</p>
                                ${calificacion(t)}
                        ${enlacePerfil(t)}
                            </div>
                            <div class="teacher-distance-box">
                                <button class="btn-contact-teacher" onclick="requestClassAccess(${t.id})">Ver Horarios</button>
                            </div>
                        `;
                        teachersContainer.appendChild(card);
                    });
                }
            }

            // 2. Tutors
            const tutorsContainer = document.getElementById('dashboard-tutors-container');
            if (tutorsContainer) {
                tutorsContainer.innerHTML = '';
                let filteredTutors = tutors;
                if (selectedTopics.length > 0) {
                    filteredTutors = filteredTutors.filter(t => 
                        t.specialties.some(spec => selectedTopics.includes(spec))
                    );
                }
                if (searchQuery) {
                    filteredTutors = filteredTutors.filter(t => 
                        normalizar(t.name).includes(searchQuery) ||
                        t.specialties.some(spec => normalizar(spec).includes(searchQuery))
                    );
                }
                
                if (filteredTutors.length === 0) {
                    tutorsContainer.innerHTML = `<div class="empty-teachers-state"><i class="bi bi-person-fill-exclamation"></i><p>No hay tutores que coincidan con tu búsqueda.</p></div>`;
                } else {
                    filteredTutors.forEach(t => {
                        const card = document.createElement('div');
                        card.className = 'teacher-card';
                        card.innerHTML = `
                            <div class="teacher-avatar">${escaparHtml(t.initial)}</div>
                            <div class="teacher-info">
                                <h4>${escaparHtml(t.name)}</h4>
                                <p class="teacher-specialty">${escaparHtml(t.specialties.join(', '))}</p>
                            </div>
                            <div class="teacher-distance-box">
                                <button class="btn-contact-teacher" onclick="requestClassAccess(${t.id})">Contactar</button>
                            </div>
                        `;
                        tutorsContainer.appendChild(card);
                    });
                }
            }

            // 3. Videos
            const videosContainer = document.getElementById('dashboard-videos-container');
            if (videosContainer) {
                videosContainer.innerHTML = '';
                let filteredVideos = videos;
                if (selectedTopics.length > 0) {
                    filteredVideos = filteredVideos.filter(v => selectedTopics.includes(v.specialty));
                }
                if (searchQuery) {
                    filteredVideos = filteredVideos.filter(v => 
                        normalizar(v.title).includes(searchQuery) ||
                        normalizar(v.specialty).includes(searchQuery) ||
                        normalizar(v.teacher).includes(searchQuery)
                    );
                }

                if (filteredVideos.length === 0) {
                    videosContainer.innerHTML = `<div class="empty-teachers-state" style="grid-column: 1/-1;"><i class="bi bi-play-btn-fill"></i><p>No hay videos de clases que coincidan con tu búsqueda.</p></div>`;
                } else {
                    filteredVideos.forEach(v => {
                        const card = document.createElement('div');
                        card.className = 'video-card';
                        card.innerHTML = `
                            <div class="video-thumbnail">
                                <div class="video-play-btn"><i class="bi bi-play-fill"></i></div>
                            </div>
                            <div class="video-info">
                                <h4 class="video-title">${escaparHtml(v.title)}</h4>
                                <span class="video-specialty">${escaparHtml(v.specialty)}</span>
                                <div class="video-meta">
                                    <span><i class="bi bi-person-video"></i> ${escaparHtml(v.teacher)}</span>
                                    <span><i class="bi bi-clock"></i> ${escaparHtml(v.duration)}</span>
                                </div>
                            </div>
                        `;
                        videosContainer.appendChild(card);
                    });
                }
            }
        }

        // Favorites Tab
        function renderFavorites() {
            const container = document.getElementById('favorites-teachers-container');
            if (!container) return;
            container.innerHTML = '';

            const favTeachers = teachers.filter(t => isFavorite(t.id));

            if (favTeachers.length === 0) {
                container.innerHTML = `
                    <div class="empty-teachers-state">
                        <i class="bi bi-star"></i>
                        <p>No has guardado profesores favoritos todavía. ¡Haz clic en la estrella de cualquier profesor en el panel de clases para guardarlo!</p>
                    </div>
                `;
                return;
            }

            favTeachers.forEach(t => {
                const card = document.createElement('div');
                card.className = 'teacher-card';
                card.innerHTML = `
                    <button type="button" class="teacher-star-btn" aria-label="Marcar profesor como favorito" onclick="toggleFavorite(${t.id}, event)">
                        <i class="bi bi-star-fill"></i>
                    </button>
                    <div class="teacher-avatar">${escaparHtml(t.initial)}</div>
                    <div class="teacher-info">
                        <h4>${escaparHtml(t.name)}</h4>
                        <p class="teacher-specialty">${escaparHtml(t.specialties.join(', '))}</p>
                        ${calificacion(t)}
                        ${enlacePerfil(t)}
                    </div>
                    <div class="teacher-distance-box">
                        <button class="btn-contact-teacher" onclick="requestClassAccess(${t.id})">Ver Horarios</button>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        // ── CLASSES RENDERING ──
        function renderMyClasses() {
            // Renderizado dinámicamente desde el backend de Django con mis_inscripciones y clases_disponibles
        }

        // ── SUPPORT RENDERING ──
        function renderMyReports() {
            // Desactivado: Ahora los reportes se renderizan con Django desde el backend
        }

        // Tab selection switching
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                tabButtons.forEach(b => b.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));

                btn.classList.add('active');
                const targetTab = btn.getAttribute('data-tab');
                const targetEl = document.getElementById(targetTab);
                if (targetEl) targetEl.classList.add('active');
            });
        });

        // ── LÓGICA DE LAS VISTAS PREMIUM ──

        function filterChatContacts() {
            const query = document.getElementById('chat-search-input')?.value.toLowerCase() || '';
            const items = document.querySelectorAll('.chat-contact-item');
            items.forEach(item => {
                const name = item.querySelector('.contact-name')?.innerText.toLowerCase() || '';
                const meta = item.querySelector('.contact-meta')?.innerText.toLowerCase() || '';
                if (name.includes(query) || meta.includes(query)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        }
