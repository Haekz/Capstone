import mongomock
from django.test import TestCase

from comunidad import esquemas, mongo
from user_profesor import almacen_videos

R2_PRUEBA = 'https://r2.test/'  # donde "firma" sus enlaces el R2 de mentira


class MongoTestCase(TestCase):
    """Usa mongomock en memoria (base lbwus_test): nunca se conecta a Atlas."""

    def setUp(self):
        super().setUp()
        mongo.usar_cliente(mongomock.MongoClient(), db='lbwus_test')
        esquemas.crear_indices(mongo.get_db())

    def tearDown(self):
        mongo.restablecer()
        super().tearDown()


class R2Falso:
    """Cloudflare R2 de mentira, en memoria: solo lo que usa almacen_videos (subir, firmar un enlace y borrar)."""

    def __init__(self):
        self.objetos = {}  # {clave: (contenido, content_type)}

    def upload_fileobj(self, archivo, bucket, clave, ExtraArgs=None):
        self.objetos[clave] = (archivo.read(), (ExtraArgs or {}).get('ContentType'))

    def generate_presigned_url(self, operacion, Params, ExpiresIn):
        return f'{R2_PRUEBA}{Params["Key"]}?vence={ExpiresIn}'

    def delete_object(self, Bucket, Key):
        self.objetos.pop(Key, None)  # como S3: borrar lo que no existe no es error


class VideosTestCase(MongoTestCase):
    """MongoTestCase con un R2 de mentira (los archivos de video): nunca se conecta a Cloudflare."""

    def setUp(self):
        super().setUp()
        self.r2 = R2Falso()
        almacen_videos.usar_cliente(self.r2)

    def tearDown(self):
        almacen_videos.restablecer()
        super().tearDown()
