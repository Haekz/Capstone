from django.http import JsonResponse
from django.views.decorators.http import require_GET

from alumnos.decorators import admin_required_json

from . import mongo


@require_GET
@admin_required_json
def salud(request):
    """Estado de MongoDB para el administrador. Nunca muestra la URI."""
    try:
        latencia = mongo.ping()
    except mongo.MongoNoConfigurado:
        return JsonResponse({'mongodb': 'no_configurado'}, status=503)
    except Exception as exc:
        mongo.logger.warning('Salud de MongoDB: %s', type(exc).__name__)
        return JsonResponse(
            {'mongodb': 'error', 'detalle': type(exc).__name__}, status=503
        )
    return JsonResponse(
        {'mongodb': 'ok', 'base': mongo.nombre_db(), 'latencia_ms': latencia}
    )
