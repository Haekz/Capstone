"""Base de las pruebas de videos: un Cloudflare R2 de mentira, en memoria. Nunca se conecta a Cloudflare.

Las fichas (tabla Video) van a la base de pruebas de Django, como todo lo demas.
"""

from django.test import TestCase

from user_profesor import almacen_videos

R2_PRUEBA = 'https://r2.test/'  # donde "firma" sus enlaces el R2 de mentira


class R2Falso:
    """Cloudflare R2 de mentira: solo lo que usa almacen_videos (subir, firmar un enlace y borrar)."""

    def __init__(self):
        self.objetos = {}  # {clave: (contenido, content_type)}

    def upload_fileobj(self, archivo, bucket, clave, ExtraArgs=None):
        self.objetos[clave] = (archivo.read(), (ExtraArgs or {}).get('ContentType'))

    def generate_presigned_url(self, operacion, Params, ExpiresIn):
        return f'{R2_PRUEBA}{Params["Key"]}?vence={ExpiresIn}'

    def delete_object(self, Bucket, Key):
        self.objetos.pop(Key, None)  # como S3: borrar lo que no existe no es error


class VideosTestCase(TestCase):
    """TestCase con un R2 de mentira (los archivos de video)."""

    def setUp(self):
        super().setUp()
        self.r2 = R2Falso()
        almacen_videos.usar_cliente(self.r2)

    def tearDown(self):
        almacen_videos.restablecer()
        super().tearDown()
