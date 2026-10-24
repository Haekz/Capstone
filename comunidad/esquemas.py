"""Unica fuente de verdad del diseño de colecciones de MongoDB.

Ver .ia/PLAN_MONGODB.md, seccion 3. Los IDs enteros apuntan a PostgreSQL
(usuario_id -> CustomUser.id, alumno_id -> Alumno.id_alumno, etc.).
"""

from pymongo import ASCENDING, DESCENDING, IndexModel

TTL_ACTIVIDAD_SEGUNDOS = 180 * 24 * 3600  # 180 dias

ACCIONES_ACTIVIDAD = [
    'login', 'login_fallido', 'logout', 'registro', 'inscripcion',
    'pago_iniciado', 'pago_confirmado', 'pago_rechazado',
    'titulo_subido', 'titulo_resuelto', 'retiro_solicitado',
]

VALIDATION_LEVEL = 'strict'
VALIDATION_ACTION = 'error'

ENTERO = {'bsonType': ['int', 'long']}
ENTERO_O_NULL = {'bsonType': ['int', 'long', 'null']}
STRING_O_NULL = {'bsonType': ['string', 'null']}
FECHA = {'bsonType': 'date'}
BOOL = {'bsonType': 'bool'}


def _esquema(required, properties):
    return {
        '$jsonSchema': {
            'bsonType': 'object',
            'required': required,
            'additionalProperties': True,
            'properties': properties,
        }
    }


COLECCIONES = {
    'actividad': {
        'validador': _esquema(
            ['accion', 'fecha'],
            {
                'usuario_id': ENTERO_O_NULL,
                'rol': STRING_O_NULL,
                'accion': {'bsonType': 'string', 'enum': ACCIONES_ACTIVIDAD},
                'detalle': {'bsonType': 'object'},
                'ip': STRING_O_NULL,
                'fecha': FECHA,
            },
        ),
        'indices': [
            IndexModel([('usuario_id', ASCENDING), ('fecha', DESCENDING)],
                       name='usuario_fecha'),
            IndexModel([('accion', ASCENDING), ('fecha', DESCENDING)],
                       name='accion_fecha'),
            IndexModel([('fecha', ASCENDING)], name='ttl_fecha',
                       expireAfterSeconds=TTL_ACTIVIDAD_SEGUNDOS),
        ],
    },
    'notificaciones': {
        'validador': _esquema(
            ['usuario_id', 'tipo', 'titulo', 'mensaje', 'leida', 'fecha'],
            {
                'usuario_id': ENTERO,
                'tipo': {'bsonType': 'string'},
                'titulo': {'bsonType': 'string', 'minLength': 1, 'maxLength': 120},
                'mensaje': {'bsonType': 'string', 'minLength': 1, 'maxLength': 500},
                'url': STRING_O_NULL,
                'leida': BOOL,
                'fecha': FECHA,
            },
        ),
        'indices': [
            IndexModel([('usuario_id', ASCENDING), ('leida', ASCENDING),
                        ('fecha', DESCENDING)],
                       name='usuario_leida_fecha'),
        ],
    },
    'resenas': {
        'validador': _esquema(
            ['profesor_id', 'alumno_id', 'inscripcion_id', 'puntaje',
             'visible', 'fecha'],
            {
                'profesor_id': ENTERO,
                'alumno_id': ENTERO,
                'inscripcion_id': ENTERO,
                'puntaje': {'bsonType': 'int', 'minimum': 1, 'maximum': 5},
                'comentario': {'bsonType': ['string', 'null'], 'maxLength': 1000},
                'visible': BOOL,
                'fecha': FECHA,
            },
        ),
        'indices': [
            IndexModel([('inscripcion_id', ASCENDING)], name='inscripcion_unica',
                       unique=True),
            IndexModel([('profesor_id', ASCENDING), ('fecha', DESCENDING)],
                       name='profesor_fecha'),
        ],
    },
    'conversaciones': {
        'validador': _esquema(
            ['alumno_id', 'profesor_id', 'creada', 'actualizada', 'no_leidos'],
            {
                'alumno_id': ENTERO,
                'profesor_id': ENTERO,
                'creada': FECHA,
                'actualizada': FECHA,
                'no_leidos': {
                    'bsonType': 'object',
                    'required': ['alumno', 'profesor'],
                    'properties': {
                        'alumno': {'bsonType': ['int', 'long'], 'minimum': 0},
                        'profesor': {'bsonType': ['int', 'long'], 'minimum': 0},
                    },
                },
            },
        ),
        'indices': [
            IndexModel([('alumno_id', ASCENDING), ('profesor_id', ASCENDING)],
                       name='alumno_profesor_unica', unique=True),
            IndexModel([('alumno_id', ASCENDING), ('actualizada', DESCENDING)],
                       name='alumno_actualizada'),
            IndexModel([('profesor_id', ASCENDING), ('actualizada', DESCENDING)],
                       name='profesor_actualizada'),
        ],
    },
    'mensajes': {
        'validador': _esquema(
            ['conversacion_id', 'autor_usuario_id', 'autor_rol', 'texto',
             'fecha', 'leido'],
            {
                'conversacion_id': {'bsonType': 'objectId'},
                'autor_usuario_id': ENTERO,
                'autor_rol': {'bsonType': 'string', 'enum': ['alumno', 'profesor']},
                'texto': {'bsonType': 'string', 'minLength': 1, 'maxLength': 2000},
                'fecha': FECHA,
                'leido': BOOL,
            },
        ),
        'indices': [
            IndexModel([('conversacion_id', ASCENDING), ('fecha', ASCENDING)],
                       name='conversacion_fecha'),
        ],
    },
}


def aplicar_validadores(db):
    """Crea cada coleccion con su validador o lo actualiza. Idempotente.

    Devuelve {nombre: 'creado' | 'actualizado'}. mongomock no soporta
    validadores: esto solo se prueba contra Atlas (test_atlas.py).
    """
    existentes = set(db.list_collection_names())
    resultado = {}
    for nombre, definicion in COLECCIONES.items():
        if nombre in existentes:
            db.command({
                'collMod': nombre,
                'validator': definicion['validador'],
                'validationLevel': VALIDATION_LEVEL,
                'validationAction': VALIDATION_ACTION,
            })
            resultado[nombre] = 'actualizado'
        else:
            db.create_collection(
                nombre,
                validator=definicion['validador'],
                validationLevel=VALIDATION_LEVEL,
                validationAction=VALIDATION_ACTION,
            )
            resultado[nombre] = 'creado'
    return resultado


def crear_indices(db):
    """Crea los indices declarados. Idempotente.

    Devuelve {nombre: [nombres de indices]}.
    """
    return {
        nombre: db[nombre].create_indexes(definicion['indices'])
        for nombre, definicion in COLECCIONES.items()
    }
