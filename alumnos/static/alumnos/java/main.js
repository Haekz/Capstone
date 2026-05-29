document.addEventListener('DOMContentLoaded', function() {
    // Modal interaction
    const openModal = document.querySelector('.mi-boton');
    const modal = document.querySelector('.modal');
    const closeModal = document.querySelector('.modal__close');

    if (openModal && closeModal && modal) {
        openModal.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.add('modal--show');
        });

        closeModal.addEventListener('click', (e) => {
            e.preventDefault();
            modal.classList.remove('modal--show');
        });
    } else {
        console.log('One of the modal elements is missing.');
    }

    // Validación de formulario de Registro
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', function(event) {
            if (!validateRegisterForm()) {
                event.preventDefault(); 
            }
        });
    }

    function validateRegisterForm() {
        return validateFullName('full-name') && validateEmailRegister('email-register') && 
               validatePassword('password-register') && validateConfirmPassword('password-register', 'confirm-password') && 
               validateBirthdate('birthdate') && validatePhone('phone');
    }

    function validateFullName(id) {
        const fullName = document.getElementById(id).value;
        const nameRegex = /^[A-Za-z\s]+$/;
        if (fullName.trim().length < 6 || !nameRegex.test(fullName)) {
            alert('El nombre debe tener al menos 6 caracteres y solo contener letras.');
            return false;
        }
        return true;
    }

    function validateEmailRegister(id) {
        const email = document.getElementById(id).value;
        const emailRegex = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,6}$/;
        if (!emailRegex.test(email)) {
            alert('Por favor ingresa un correo electrónico válido.');
            return false;
        }
        return true;
    }

    function validatePassword(id) {
        const password = document.getElementById(id).value;
        if (password.length < 6) {
            alert('La contraseña debe tener al menos 6 caracteres.');
            return false;
        }
        return true;
    }

    function validateConfirmPassword(passwordId, confirmPasswordId) {
        const password = document.getElementById(passwordId).value;
        const confirmPassword = document.getElementById(confirmPasswordId).value;
        if (confirmPassword !== password) {
            alert('Las contraseñas no coinciden.');
            return false;
        }
        return true;
    }

    function validateBirthdate(id) {
        const birthdate = document.getElementById(id).value;
        if (!birthdate) {
            alert('El campo de fecha de nacimiento es requerido.');
            return false;
        }
        const birthDateObject = new Date(birthdate);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const eighteenYearsAgo = new Date(today.getFullYear() - 18, today.getMonth(), today.getDate());
        if (birthDateObject > eighteenYearsAgo) {
            alert('Debes tener al menos 18 años de edad.');
            return false;
        }
        return true;
    }

    function validatePhone(id) {
        const phone = document.getElementById(id).value;
        const phoneRegex = /^[0-9]{9}$/;
        if (!phoneRegex.test(phone)) {
            alert('Por favor ingresa un número de teléfono válido de 9 dígitos.');
            return false;
        }
        return true;
    }

    // Validación de formulario de Contacto
    const contactForm = document.getElementById('contact-form');
    if (contactForm) {
        contactForm.addEventListener('submit', function(event) {
            if (!validateContactForm()) {
                event.preventDefault(); // Prevent form submission if validation fails
            }
        });
    }

    function validateContactForm() {
        return validateContactName('nombre') && validateContactEmail('email-contact') && validateContactMessage('mensaje');
    }

    function validateContactName(id) {
        const contactName = document.getElementById(id).value;
        if (contactName.trim().length === 0) {
            alert('Por favor ingresa tu nombre.');
            return false;
        }
        return true;
    }

    function validateContactEmail(id) {
        return validateEmailRegister(id);  // Reuse the email validation function
    }

    function validateContactMessage(id) {
        const contactMessage = document.getElementById(id).value;
        if (contactMessage.trim().length === 0) {
            alert('Por favor ingresa tu mensaje.');
            return false;
        }
        return true;
    }

    // Función de cambio de tema claro y oscuro
    const themeToggler = document.getElementById('theme-toggler');
    if (themeToggler) {
        themeToggler.addEventListener('click', function() {
            const body = document.body;
            body.classList.toggle('dark-theme'); // Cambia la clase para aplicar el tema oscuro

            const icon = themeToggler.querySelector('i');  // Encuentra el ícono dentro del botón
            if (body.classList.contains('dark-theme')) {
                icon.classList.remove('bi-sun');
                icon.classList.add('bi-sun-fill');
            } else {
                icon.classList.remove('bi-sun-fill');
                icon.classList.add('bi-sun');
            }
        });
    }
});

document.addEventListener('DOMContentLoaded', function() {
    const listaCursos = document.getElementById('lista-cursos');
    const tbody = document.querySelector('#lista-carrito tbody');
    const contadorCarrito = document.querySelector('#contador-carrito');
    let articulosCarrito = cargarCarritoDeLocalStorage();

    if (tbody) {
        actualizarCarrito();
    }

    if (listaCursos) {
        listaCursos.addEventListener('click', function(e) {
            if (e.target.classList.contains('agregar-carrito')) {
                const cursoCard = e.target.closest('.card');
                agregarCursoAlCarrito(cursoCard);
            }
        });
    }

    if (tbody) {
        tbody.addEventListener('click', function(e) {
            if (e.target.classList.contains('borrar-curso')) {
                eliminarCursoDelCarrito(e.target);
            }
        });
    }

    function agregarCursoAlCarrito(curso) {
        const infoCurso = {
            id: curso.querySelector('button').getAttribute('data-id'),
            titulo: curso.querySelector('h3').textContent,
            precio: curso.querySelector('span').textContent,
            cantidad: 1
        };

        const existe = articulosCarrito.some(curso => curso.id === infoCurso.id);
        if (existe) {
            articulosCarrito = articulosCarrito.map(curso => curso.id === infoCurso.id ? {...curso, cantidad: curso.cantidad + 1} : curso);
        } else {
            articulosCarrito.push(infoCurso);
        }
        guardarCarritoEnLocalStorage();
        actualizarCarrito();
    }

    function eliminarCursoDelCarrito(elemento) {
        const id = elemento.getAttribute('data-id');
        articulosCarrito = articulosCarrito.filter(curso => curso.id !== id);
        guardarCarritoEnLocalStorage();
        actualizarCarrito();
    }

    function actualizarCarrito() {
        limpiarHTML();
        if (tbody) {
            articulosCarrito.forEach(curso => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${curso.titulo}</td>
                    <td>${curso.precio}</td>
                    <td>${curso.cantidad}</td>
                    <td><button class="borrar-curso" data-id="${curso.id}">X</button></td>
                `;
                tbody.appendChild(row);
            });
        }
        actualizarContadorCarrito();
        // Mostrar el carrito si hay artículos
        const carritoEl = document.getElementById('carrito');
        if (carritoEl) {
            carritoEl.style.display = articulosCarrito.length > 0 ? 'block' : 'none';
        }
    }

    function limpiarHTML() {
        if (tbody) {
            while (tbody.firstChild) {
                tbody.removeChild(tbody.firstChild);
            }
        }
    }

    function guardarCarritoEnLocalStorage() {
        localStorage.setItem('carrito', JSON.stringify(articulosCarrito));
    }

    function cargarCarritoDeLocalStorage() {
        return localStorage.getItem('carrito') ? JSON.parse(localStorage.getItem('carrito')) : [];
    }

    function actualizarContadorCarrito() {
        const totalArticulos = articulosCarrito.reduce((total, curso) => total + curso.cantidad, 0);
        if (contadorCarrito) {
            contadorCarrito.textContent = totalArticulos;
        }
    }
});



