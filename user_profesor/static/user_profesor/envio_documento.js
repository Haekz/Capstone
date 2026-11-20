// Envio por fetch de los documentos del panel del profesor (titulo y especializaciones).
// Cada formulario lleva data-envio-documento; la vista responde {success, message}.
(function () {
    // Si el CDN de SweetAlert no carga, el profesor igual debe enterarse.
    function avisar(titulo, texto, icono) {
        if (window.Swal) {
            return Swal.fire({ title: titulo, text: texto, icon: icono, confirmButtonColor: '#7c3aed' });
        }
        alert(titulo + '\n\n' + texto);
        return Promise.resolve();
    }

    document.querySelectorAll('form[data-envio-documento]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const boton = form.querySelector('button');
            boton.disabled = true;
            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value }
            })
            .then(r => r.json())
            .then(data => avisar(
                data.success ? '¡Recibido!' : 'Revisa los datos',
                data.message,
                data.success ? 'success' : 'warning'
            ).then(() => { if (data.success) window.location.reload(); }))
            .catch(() => avisar('Error', 'No pudimos subir el archivo.', 'error'))
            .finally(() => { boton.disabled = false; });
        });
    });
})();
