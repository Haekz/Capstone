{# Parte del <script> principal de alumnos/Alumno_pag1.html: se incluye dentro de el (no es un archivo estatico). #}
        // ── MANDATORY PLAN ACCESS VERIFICATION & CLASS SCHEDULING ──
        const requestClassAccess = (teacherId) => {
            switchView('view-my-classes');
            setTimeout(() => {
                const targetEl = document.getElementById('catalogo-clases-seccion');
                if (targetEl) targetEl.scrollIntoView({ behavior: 'smooth' });
            }, 100);
        };

        function inscribirAClase(idClase, nombreCurso) {
            Swal.fire({
                title: 'Confirmar Inscripción',
                text: `¿Deseas inscribirte a la clase "${nombreCurso}"?`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, Inscribirme',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: 'var(--primary)',
                cancelButtonColor: '#6b7280'
            }).then((result) => {
                if (result.isConfirmed) {
                    fetch("{% url 'inscribir_clase' %}", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": "{{ csrf_token }}"
                        },
                        body: JSON.stringify({ id_clase: idClase })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.success) {
                            Swal.fire({
                                title: '¡Inscripción Exitosa!',
                                text: data.message,
                                icon: 'success',
                                confirmButtonColor: 'var(--primary)'
                            }).then(() => {
                                window.location.reload();
                            });
                        } else {
                            Swal.fire({
                                title: 'Atención',
                                text: data.message,
                                icon: 'warning',
                                confirmButtonColor: 'var(--primary)'
                            });
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire('Error', 'No se pudo procesar la inscripción.', 'error');
                    });
                }
            });
        }
        window.inscribirAClase = inscribirAClase;

        // ── RESTORE INTERESTS FROM STORAGE ──
        const savedTopics = JSON.parse(localStorage.getItem('selected-topics') || '[]');
        const topicButtons = document.querySelectorAll('.topic-tag');
        topicButtons.forEach(btn => {
            const topic = btn.getAttribute('data-topic');
            if (savedTopics.includes(topic)) {
                btn.classList.add('selected');
            }

            btn.addEventListener('click', () => {
                btn.classList.toggle('selected');
                renderModalPreview();
            });
        });

        function getSelectedTopics() {
            const selected = [];
            document.querySelectorAll('.topic-tag.selected').forEach(btn => {
                selected.push(btn.getAttribute('data-topic'));
            });
            return selected;
        }
