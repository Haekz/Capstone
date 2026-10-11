import mongomock
from django.test import TestCase

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
