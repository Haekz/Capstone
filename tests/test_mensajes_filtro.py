"""Filtro de datos de contacto, version moderada (paso C1a, decidido 02-nov). Datos ficticios."""

from django.test import SimpleTestCase

from mensajes.filtro import ContactoBloqueado, exigir_sin_contacto, motivo

BLOQUEADOS = {
    'un teléfono': [
        'mi numero es +56 9 8765 4321', 'llamame al 987654321', 'es el 9-8765-4321', 'anota 9.8765.4321',
        'fono (2) 2345 6789', 'escribeme al 56987654321', 'mi cel: 9 8765 4321 por si acaso',
    ],
    'un correo electrónico': [
        'escribeme a ana@gmail.com', 'mi correo ana arroba gmail punto com', 'ana (at) gmail',
        'ana@hotmail', 'te paso algo en gmail punto com',
    ],
    'una red social o app de mensajería': [
        'te paso mi whatsapp', 'hablemos por WhatsApp', 'mi insta es ana_clases', 'por telegram mejor',
        'agregame al wsp', 'busca mi facebook',
    ],
    'una dirección': [
        'vivo en calle los aromos 123', 'Avenida Providencia 1234', 'av. libertador bernardo ohiggins 1234',
        'pje los olmos #45', 'mi dirección es cerca del metro', 'Mi Direccion la paso luego',
    ],
}

PERMITIDOS = [
    'Nos vemos a las 15:00', 'La clase cuesta $15.000', 'Haz los ejercicios 12 al 25 de la página 134',
    'El 12-03-2026 a las 15:00 te parece?', 'Tengo prueba el 20/03/2026', 'Resolví 3 de 5 problemas del capítulo 2',
    'Mi nota fue 6,5 y la anterior 5,8', 'Gracias profe, hasta el lunes', 'El pasaje 3 del texto es difícil',
    'Cambio la hora? el martes a las 17', 'La dirección del vector es hacia el norte', 'Compré el paquete de 8 clases',
    'Instalé el programa y funciona', 'Por favor revisa el ejercicio 1.250 del libro', 'Son 4 clases por 59.000',
    'En la calle de la vida real las cosas cambian', 'Mi hermano tiene 12 años y yo 15',
]


class FiltroDeContactoTests(SimpleTestCase):

    def test_bloquea_y_dice_que_encontro(self):
        for esperado, textos in BLOQUEADOS.items():
            for texto in textos:
                with self.subTest(texto=texto):
                    self.assertEqual(motivo(texto), esperado)

    def test_deja_pasar_numeros_y_palabras_normales(self):
        for texto in PERMITIDOS:
            with self.subTest(texto=texto):
                self.assertIsNone(motivo(texto))
                exigir_sin_contacto(texto)

    def test_el_error_explica_sin_repetir_el_texto(self):
        with self.assertRaises(ContactoBloqueado) as cm:
            exigir_sin_contacto('llamame al 987654321')
        mensaje = cm.exception.messages[0]
        self.assertEqual(mensaje, 'No puedes compartir un teléfono por aquí. Coordinen las clases dentro de LBWUS.')
        self.assertNotIn('987654321', mensaje)
