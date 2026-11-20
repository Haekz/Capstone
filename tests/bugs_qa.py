"""Pruebas que documentan un bug abierto de la revision QA (docs/PRUEBAS.md).

``@bug_qa('BUG-QA-01', 'motivo')`` marca la prueba como fallo esperado:
``pytest.mark.xfail(strict=True)`` con pytest y ``unittest.expectedFailure`` con
``manage.py test``. Se usa una sola de las dos: juntas, pytest toma el "exito
inesperado" de unittest como el fallo esperado y no avisa. Si el bug se corrige,
la prueba pasa y la suite falla en ambos runners: ahi se quita la marca.
"""

import unittest

# conftest.py lo pone en True: el decorador corre al importar el modulo de pruebas,
# despues de conftest.
EN_PYTEST = False


def bug_qa(id_bug, motivo):
    def marcar(prueba):
        if EN_PYTEST:
            import pytest
            return pytest.mark.xfail(strict=True, reason=f'{id_bug}: {motivo}')(prueba)
        return unittest.expectedFailure(prueba)
    return marcar
