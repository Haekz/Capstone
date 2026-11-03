"""Documentos por revisar: carnet del apoderado y documento del vinculo.

Se guardan cifrados en la base de datos (PostgreSQL), nunca en disco: Railway borra
el disco en cada deploy. JPG o PNG: al subirlos se vuelven a codificar, asi se
descartan archivos que no son imagenes y se borran sus metadatos (por ejemplo, la
ubicacion GPS de una foto). PDF (N6): se guarda el original cifrado y nunca va al
navegador; al verlo se convierte a imagen (pypdfium2) en el servidor. Al verlos se les
pone marca de agua con el nombre de quien los abre. Se borran al aprobar o rechazar la
revision, o a los 30 dias.
"""

import io

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from cryptography.fernet import MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from alumnos.cifrado import cifrador

TAMANO_MAXIMO = 5 * 1024 * 1024
LADO_MAXIMO = 2000  # pixeles: suficiente para leer un carnet o un certificado
FORMATOS = ('JPEG', 'PNG')
MAX_PAGINAS = 3  # PDF: "pocas paginas" (N6); decidido 02-nov
ANCHO_PAGINA = 1400  # pixeles de cada pagina de un PDF al convertirla a imagen
SEPARACION = 16  # pixeles entre paginas
ERROR_FORMATO = f'Sube una foto o imagen JPG o PNG, o un PDF de hasta {MAX_PAGINAS} páginas.'
ERROR_PDF_CLAVE = 'El PDF tiene contraseña. Quítasela y vuelve a subirlo.'
ERROR_PDF_PAGINAS = f'El PDF puede tener hasta {MAX_PAGINAS} páginas.'


def _cifrador():
    """Cifra con DOCUMENTOS_CLAVE; descifra con ella o con la clave derivada de SECRET_KEY.

    La derivada solo sirve para leer lo subido antes de definir DOCUMENTOS_CLAVE
    (viven 30 dias como maximo). Si se rota SECRET_KEY, lo cifrado con la derivada
    ya no se lee y hay que pedirlo de nuevo. Por eso, con DEBUG=False,
    DOCUMENTOS_CLAVE es obligatoria (SCRUM-93); en desarrollo basta la derivada.
    """
    derivada = cifrador('documentos-apoderados')
    if settings.DOCUMENTOS_CLAVE:
        return MultiFernet([cifrador('documentos-apoderados', settings.DOCUMENTOS_CLAVE), derivada])
    if not settings.DEBUG:
        raise ImproperlyConfigured('Falta la variable DOCUMENTOS_CLAVE: es obligatoria con DEBUG=False.')
    return derivada


def preparar(archivo):
    """Valida el documento subido y lo devuelve cifrado: (contenido, formato).

    Imagen: re-codificada, sin metadatos. PDF: el original tal cual (N6), si se puede convertir.
    """
    if archivo.size > TAMANO_MAXIMO:
        raise ValidationError('El archivo no puede superar los 5 MB.')
    if archivo.read(5) == b'%PDF-':
        archivo.seek(0)
        original = archivo.read()
        _pdf_a_imagen(original)  # se abre, sin contrasena, de 1 a 3 paginas y se puede dibujar
        return _cifrador().encrypt(original), 'PDF'
    archivo.seek(0)
    try:
        imagen = Image.open(archivo)
        formato = imagen.format
        imagen.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(ERROR_FORMATO)
    if formato not in FORMATOS:
        raise ValidationError(ERROR_FORMATO)
    imagen = ImageOps.exif_transpose(imagen)  # respeta la orientacion antes de descartar el EXIF
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    salida = io.BytesIO()
    if formato == 'JPEG':
        imagen.convert('RGB').save(salida, 'JPEG', quality=85)
    else:
        imagen.save(salida, 'PNG')
    return _cifrador().encrypt(salida.getvalue()), formato


def descifrar(contenido):
    return _cifrador().decrypt(bytes(contenido))  # PostgreSQL entrega un memoryview


def _pdf_a_imagen(original):
    """Las paginas del PDF, una bajo otra, en una sola imagen RGB. Lanza ValidationError."""
    try:
        pdf = pdfium.PdfDocument(original)
    except pdfium.PdfiumError as error:
        raise ValidationError(ERROR_PDF_CLAVE if error.err_code == pdfium_raw.FPDF_ERR_PASSWORD else ERROR_FORMATO)
    try:
        if not 1 <= len(pdf) <= MAX_PAGINAS:
            raise ValidationError(ERROR_PDF_PAGINAS)
        paginas = []
        for numero in range(len(pdf)):
            ancho, alto = pdf[numero].get_size()  # en puntos; la escala acota los pixeles en ambos lados
            escala = min(ANCHO_PAGINA / ancho, LADO_MAXIMO / alto)
            paginas.append(pdf[numero].render(scale=escala).to_pil().convert('RGB'))
    except pdfium.PdfiumError:
        raise ValidationError(ERROR_FORMATO)
    finally:
        pdf.close()
    hoja = Image.new('RGB', (max(p.width for p in paginas),
                             sum(p.height for p in paginas) + SEPARACION * (len(paginas) - 1)), 'gray')
    y = 0
    for pagina in paginas:
        hoja.paste(pagina, (0, y))
        y += pagina.height + SEPARACION
    return hoja


def texto_de_revision(usuario):
    """Texto de la marca de agua: quien abre el documento y cuando (tambien para los titulos, paso 9b)."""
    return f'LBWUS - solo revision - {usuario.first_name or usuario.username} - {timezone.localtime():%d-%m-%Y %H:%M}'


def con_marca_de_agua(contenido, texto):
    """JPEG del documento con ``texto`` repetido encima: si se filtra, se sabe quien lo abrio.

    Un PDF se entrega como imagen: el original nunca sale del servidor.
    """
    claro = descifrar(contenido)
    documento = _pdf_a_imagen(claro) if claro.startswith(b'%PDF-') else Image.open(io.BytesIO(claro))
    imagen = documento.convert('RGBA')
    ancho, alto = imagen.size
    fuente = ImageFont.load_default(size=max(14, ancho // 28))
    capa = Image.new('RGBA', imagen.size, (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    izquierda, arriba, derecha, abajo = dibujo.textbbox((0, 0), texto, font=fuente)
    paso_x, paso_y = derecha - izquierda + 40, (abajo - arriba) * 4
    for fila, y in enumerate(range(0, alto, paso_y)):
        for x in range(-(fila % 2) * paso_x // 2, ancho, paso_x):
            dibujo.text((x, y), texto, font=fuente, fill=(200, 0, 0, 110))
    salida = io.BytesIO()
    Image.alpha_composite(imagen, capa).convert('RGB').save(salida, 'JPEG', quality=85)
    return salida.getvalue()
