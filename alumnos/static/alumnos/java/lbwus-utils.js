/**
 * Utilidades compartidas de LBWUS. Una sola copia de escaparHtml (escape anti-XSS, S-23):
 * antes vivia en base.html y base_admin.html la duplicaba como respaldo (PR #107, Franco).
 */
(function (global) {
    'use strict';

    function escaparHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    global.escaparHtml = escaparHtml;
})(window);
