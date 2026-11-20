from types import SimpleNamespace

import mongomock
from django.test import TestCase
from mongomock.gridfs import enable_gridfs_integration

from comunidad import esquemas, mongo


class MongoTestCase(TestCase):
    """Usa mongomock en memoria (base lbwus_test): nunca se conecta a Atlas."""

    def setUp(self):
        super().setUp()
        mongo.usar_cliente(mongomock.MongoClient(), db='lbwus_test')
        esquemas.crear_indices(mongo.get_db())

    def tearDown(self):
        mongo.restablecer()
        super().tearDown()


class GridFsTestCase(MongoTestCase):
    """MongoTestCase con GridFS (videos).

    enable_gridfs_integration() parcha gridfs con mock.patch(...).start(), y otras pruebas (test_puerta) cierran con
    patch.stopall(), que deshace tambien ese parche: por eso se activa en cada setUp y no una vez al importar.
    """

    def setUp(self):
        super().setUp()
        enable_gridfs_integration()
        # GridFS de pymongo lee client.options.timeout; mongomock no lo trae. Sin limite, como pymongo por omision.
        mongo.get_client().options = SimpleNamespace(timeout=None)
