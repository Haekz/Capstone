"""Pruebas de integracion contra MongoDB Atlas (base lbwus_test).

Se omiten salvo que existan MONGODB_URI y MONGODB_INTEGRACION=1:
    MONGODB_INTEGRACION=1 python manage.py test comunidad.tests.test_atlas

mongomock no aplica validadores $jsonSchema: aqui se comprueban de verdad.
"""

import os
import unittest
from datetime import datetime, timezone

from django.test import SimpleTestCase
from pymongo.errors import WriteError

from comunidad import esquemas, mongo

BASE_PRUEBAS = 'lbwus_test'  # Nunca lbwus_dev ni lbwus_prod.


@unittest.skipUnless(
    os.environ.get('MONGODB_URI') and os.environ.get('MONGODB_INTEGRACION') == '1',
    'Pruebas de Atlas: requieren MONGODB_URI y MONGODB_INTEGRACION=1.',
)
class AtlasTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mongo.restablecer()
        cliente = mongo.get_client()  # Cliente real, con la URI del entorno.
        mongo.usar_cliente(cliente, db=BASE_PRUEBAS)
        cls.db = mongo.get_db()
        assert cls.db.name == BASE_PRUEBAS
        esquemas.aplicar_validadores(cls.db)
        esquemas.crear_indices(cls.db)

    @classmethod
    def tearDownClass(cls):
        try:
            mongo.get_client().drop_database(BASE_PRUEBAS)
        finally:
            mongo.restablecer()
            super().tearDownClass()

    def test_usa_solo_la_base_de_pruebas(self):
        self.assertEqual(mongo.nombre_db(), BASE_PRUEBAS)
        self.assertEqual(self.db.name, BASE_PRUEBAS)

    def test_validadores_e_indices_son_idempotentes(self):
        resultado = esquemas.aplicar_validadores(self.db)
        self.assertEqual(set(resultado.values()), {'actualizado'})
        esquemas.crear_indices(self.db)
        self.assertTrue(set(esquemas.COLECCIONES) <= set(self.db.list_collection_names()))

    def test_actividad_sin_accion_es_rechazada(self):
        with self.assertRaises(WriteError) as ctx:
            self.db.actividad.insert_one({'fecha': datetime.now(timezone.utc)})
        self.assertEqual(ctx.exception.code, 121)

    def test_resena_con_puntaje_6_es_rechazada(self):
        with self.assertRaises(WriteError) as ctx:
            self.db.resenas.insert_one({
                'profesor_id': 1, 'alumno_id': 2, 'inscripcion_id': 999,
                'puntaje': 6, 'visible': True,
                'fecha': datetime.now(timezone.utc),
            })
        self.assertEqual(ctx.exception.code, 121)

    def test_resena_valida_es_aceptada(self):
        self.db.resenas.insert_one({
            'profesor_id': 1, 'alumno_id': 2, 'inscripcion_id': 1000,
            'puntaje': 5, 'comentario': None, 'visible': True,
            'fecha': datetime.now(timezone.utc),
        })

    def test_ttl_de_actividad_es_de_180_dias(self):
        info = self.db.actividad.index_information()
        self.assertEqual(info['ttl_fecha']['expireAfterSeconds'], 180 * 24 * 3600)
