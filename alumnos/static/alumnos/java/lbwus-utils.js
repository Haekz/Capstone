/**
 * Utilidades compartidas LBWUS (Seguridad DOM XSS, Formato CLP y Carrito Global DRY).
 */
(function (global) {
    'use strict';

    var PERIODOS = [
        { valor: 'mensual', label: 'Mensual', factor: 1 },
        { valor: '3semanas', label: '3 Semanas', factor: 0.75 },
        { valor: '2semanas', label: '2 Semanas', factor: 0.50 },
        { valor: '1semana', label: '1 Semana', factor: 0.25 }
    ];

    function escaparHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatoCLP(valor) {
        var n = Math.round(Number(valor) || 0);
        return '$' + n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    }

    function parsePrecioCLP(precioStr) {
        return parseInt(String(precioStr || '0').replace(/[^0-9]/g, ''), 10) || 0;
    }

    var articulos = [];

    function cargarArticulos() {
        try {
            articulos = JSON.parse(localStorage.getItem('carrito')) || [];
            if (!Array.isArray(articulos)) articulos = [];
        } catch (e) {
            articulos = [];
        }
        articulos.forEach(function (a) {
            if (!a.periodo) a.periodo = 'mensual';
        });
    }

    function guardarArticulos() {
        localStorage.setItem('carrito', JSON.stringify(articulos));
    }

    function actualizarContador() {
        var c = document.getElementById('contador-carrito') || document.getElementById('cart-count');
        if (!c) return;
        var total = articulos.reduce(function (s, a) { return s + (parseInt(a.cantidad, 10) || 1); }, 0);
        c.textContent = String(total);
        c.style.display = total > 0 ? 'flex' : 'none';
    }

    function renderCarritoGlobal() {
        var tbody = document.querySelector('#lista-carrito tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (articulos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:12px;color:var(--text-light)">Sin planes en el carrito</td></tr>';
        } else {
            articulos.forEach(function (item) {
                var pObj = PERIODOS.find(function (p) { return p.valor === (item.periodo || 'mensual'); }) || PERIODOS[0];
                var precioAjustado = Math.round(parsePrecioCLP(item.precio) * pObj.factor);
                var opciones = PERIODOS.map(function (p) {
                    var sel = p.valor === (item.periodo || 'mensual') ? 'selected' : '';
                    return '<option value="' + escaparHtml(p.valor) + '" ' + sel + '>' + escaparHtml(p.label) + '</option>';
                }).join('');

                var tr = document.createElement('tr');
                tr.innerHTML =
                    '<td class="cart-item-name">' + escaparHtml(item.titulo) + '</td>' +
                    '<td><select class="cart-periodo-select" data-id="' + escaparHtml(item.id) + '">' + opciones + '</select></td>' +
                    '<td class="cart-item-price">' + escaparHtml(formatoCLP(precioAjustado)) + '</td>' +
                    '<td>' + escaparHtml(item.cantidad) + '</td>' +
                    '<td><button class="cart-remove-btn" data-id="' + escaparHtml(item.id) + '">&times;</button></td>';
                tbody.appendChild(tr);
            });
        }

        actualizarContador();
        var btnPagar = document.getElementById('btn-ir-pago');
        if (btnPagar) btnPagar.style.display = articulos.length > 0 ? 'block' : 'none';

        tbody.querySelectorAll('.cart-periodo-select').forEach(function (sel) {
            sel.addEventListener('change', function () {
                var item = articulos.find(function (a) { return String(a.id) === String(sel.dataset.id); });
                if (item) {
                    item.periodo = sel.value;
                    guardarArticulos();
                    renderCarritoGlobal();
                }
            });
        });

        tbody.querySelectorAll('.cart-remove-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                articulos = articulos.filter(function (a) { return String(a.id) !== String(btn.dataset.id); });
                guardarArticulos();
                renderCarritoGlobal();
            });
        });
    }

    function cargarCarritoGlobal() {
        cargarArticulos();
        renderCarritoGlobal();
    }

    global.agregarAlCarrito = function (id, titulo, precio) {
        cargarArticulos();
        var existe = articulos.find(function (a) { return String(a.id) === String(id); });
        if (existe) existe.cantidad = (parseInt(existe.cantidad, 10) || 1) + 1;
        else articulos.push({ id: id, titulo: titulo, precio: precio, cantidad: 1, periodo: 'mensual' });
        guardarArticulos();
        renderCarritoGlobal();
    };

    global.escaparHtml = escaparHtml;
    global.formatoCLP = formatoCLP;
    global.cargarCarritoGlobal = cargarCarritoGlobal;

    if (typeof document !== 'undefined' && document.addEventListener) {
        document.addEventListener('DOMContentLoaded', function () {
            cargarCarritoGlobal();

            var cartButton = document.getElementById('cart-button');
            var carrito = document.getElementById('carrito');
            if (cartButton && carrito && !cartButton.dataset.boundCartDropdown) {
                cartButton.dataset.boundCartDropdown = '1';
                cartButton.addEventListener('click', function (e) {
                    e.stopPropagation();
                    carrito.style.display = (carrito.style.display === 'block') ? 'none' : 'block';
                });
                document.addEventListener('click', function () {
                    carrito.style.display = 'none';
                });
                carrito.addEventListener('click', function (e) {
                    e.stopPropagation();
                });
            }

            var vaciarBtn = document.getElementById('vaciar-carrito');
            if (vaciarBtn && !vaciarBtn.dataset.boundCartClear) {
                vaciarBtn.dataset.boundCartClear = '1';
                vaciarBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    articulos = [];
                    guardarArticulos();
                    renderCarritoGlobal();
                });
            }
        });
    }
})(typeof window !== 'undefined' ? window : globalThis);
