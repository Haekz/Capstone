import datetime
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.db.models import Sum, Q
from alumnos.models import (
    Especialidad, Genero, Profesor, Clase, Inscripcion, Tutor,
    SolicitudRetiro, Pago, PlanAlumno, DesgloseOperacion, Banco,
)
from alumnos.decorators import profesor_required, profesor_required_json
from alumnos.roles import ADMIN, PROFESOR, abrir_sesion_rol
from alumnos.utils import formato_clp, validar_rut_chileno, usuario_existe, validar_imagen_perfil
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from . import foto
from alumnos import paquetes

logger = logging.getLogger(__name__)

VALOR_INSCRIPCION = 15000
COMISION_LBWUS = 2250
PAGO_PROFESOR = 12750

def _valor_clase(inscripcion):
    """Lo que pago el alumno por esa clase."""
    return inscripcion.paquete.precio_por_clase if getattr(inscripcion, 'paquete_id', None) else VALOR_INSCRIPCION


def calcular_saldos(profesor, retiros_lista=None):
    """Devuelve los saldos de un profesor a partir de sus inscripciones y planes vendidos (S4-03)."""
    from alumnos.services import PlanesService

    tarifa_base = PlanesService.obtener_tarifa_base_profesor(profesor)
    calc_ref = PlanesService.calcular_precios_plan('flexible', tarifa_base=tarifa_base)
    valor_unitario = calc_ref['precio_total']
    pago_unitario = calc_ref['monto_tutor']

    # 1. Inscripciones individuales o con Paquetes
    inscripciones_qs = Inscripcion.objects.filter(clase__profesor=profesor)
    if hasattr(inscripciones_qs, 'consumidas'):
        inscripciones_consumidas = inscripciones_qs.consumidas().select_related('paquete')
    else:
        inscripciones_consumidas = inscripciones_qs.filter(estado=Inscripcion.ESTADO_CONFIRMADA).select_related('paquete')

    valores = [_valor_clase(i) for i in inscripciones_consumidas]
    total_ganado_inscripciones = sum(valores)
    corresponde_tutor_inscripciones = sum(paquetes.pago_profesor(v) for v in valores)

    # 2. Planes vendidos asociados directamente a este profesor (PlanAlumno S4-03)
    planes = PlanAlumno.objects.filter(
        profesor=profesor,
        pago__estado=Pago.ESTADO_PAGADA,
        estado__in=[PlanAlumno.ESTADO_ACTIVO, PlanAlumno.ESTADO_AGOTADO]
    ).only('monto_total', 'monto_tutor', 'total_clases', 'clases_consumidas')

    total_ganado_planes = 0
    corresponde_tutor_planes_consumido = 0
    tutor_planes_pendiente = 0

    for plan in planes:
        total_ganado_planes += plan.monto_total
        if plan.total_clases > 0:
            monto_por_clase_tutor = plan.monto_tutor / plan.total_clases
            consumido = int(round(monto_por_clase_tutor * plan.clases_consumidas))
            pendiente_clases = plan.monto_tutor - consumido
            corresponde_tutor_planes_consumido += consumido
            tutor_planes_pendiente += pendiente_clases
        else:
            corresponde_tutor_planes_consumido += plan.monto_tutor

    total_ganado = total_ganado_inscripciones + total_ganado_planes
    bruto_tutor_acumulado = corresponde_tutor_inscripciones + corresponde_tutor_planes_consumido

    if retiros_lista is not None:
        aprobados = sum(r.monto for r in retiros_lista if r.estado == 'aprobado')
        retiros_pendientes = sum(r.monto for r in retiros_lista if r.estado == 'pendiente')
    else:
        agregados_retiros = SolicitudRetiro.objects.filter(profesor=profesor).aggregate(
            aprobados=Sum('monto', filter=Q(estado='aprobado')),
            pendientes=Sum('monto', filter=Q(estado='pendiente')),
        )
        aprobados = agregados_retiros['aprobados'] or 0
        retiros_pendientes = agregados_retiros['pendientes'] or 0

    disponible = max(0, bruto_tutor_acumulado - aprobados - retiros_pendientes)

    # Fondos pendientes: comisión retenida + saldo de clases no ejecutadas aún + retiros en trámite
    comision_plataforma = total_ganado - (bruto_tutor_acumulado + tutor_planes_pendiente)
    pendiente = comision_plataforma + tutor_planes_pendiente + retiros_pendientes

    return {
        'total_ganado': total_ganado,
        'disponible': disponible,
        'pendiente': pendiente,
    }

    # 2. Planes vendidos asociados directamente a este profesor
    planes = PlanAlumno.objects.filter(
        profesor=profesor,
        pago__estado=Pago.ESTADO_PAGADA,
        estado__in=[PlanAlumno.ESTADO_ACTIVO, PlanAlumno.ESTADO_AGOTADO]
    ).only('monto_total', 'monto_tutor', 'total_clases', 'clases_consumidas')

    total_ganado_planes = 0
    corresponde_tutor_planes_consumido = 0
    tutor_planes_pendiente = 0

    for plan in planes:
        total_ganado_planes += plan.monto_total
        if plan.total_clases > 0:
            monto_por_clase_tutor = plan.monto_tutor / plan.total_clases
            consumido = int(round(monto_por_clase_tutor * plan.clases_consumidas))
            pendiente_clases = plan.monto_tutor - consumido
            corresponde_tutor_planes_consumido += consumido
            tutor_planes_pendiente += pendiente_clases
        else:
            corresponde_tutor_planes_consumido += plan.monto_tutor

    total_ganado = total_ganado_inscripciones + total_ganado_planes
    bruto_tutor_acumulado = corresponde_tutor_inscripciones + corresponde_tutor_planes_consumido

    if retiros_lista is not None:
        aprobados = sum(r.monto for r in retiros_lista if r.estado == 'aprobado')
        retiros_pendientes = sum(r.monto for r in retiros_lista if r.estado == 'pendiente')
    else:
        agregados_retiros = SolicitudRetiro.objects.filter(profesor=profesor).aggregate(
            aprobados=Sum('monto', filter=Q(estado='aprobado')),
            pendientes=Sum('monto', filter=Q(estado='pendiente')),
        )
        aprobados = agregados_retiros['aprobados'] or 0
        retiros_pendientes = agregados_retiros['pendientes'] or 0

    disponible = max(0, bruto_tutor_acumulado - aprobados - retiros_pendientes)

    # Fondos pendientes: comisión retenida + saldo de clases no ejecutadas aún + retiros en trámite
    comision_plataforma = total_ganado - (bruto_tutor_acumulado + tutor_planes_pendiente)
    pendiente = comision_plataforma + tutor_planes_pendiente + retiros_pendientes

    return {
        'total_ganado': total_ganado,
        'disponible': disponible,
        'pendiente': pendiente,
    }


def buscar_especialidad(especialidad_id):
    """Especialidad del catalogo segun el id que manda el <select>, o None."""
    if not especialidad_id.isdecimal():
        return None
    return Especialidad.objects.filter(pk=especialidad_id).first()


# --- Vistas de Registro y Acceso de Profesor ---

def regis_prof(request):
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre', '').strip()
            rut = request.POST.get('rut', '').strip()
            especialidad_id = request.POST.get('especialidad', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            fecha_nacimiento = request.POST.get('fecha_nacimiento', '').strip()
            correo_electronico = request.POST.get('correo_electronico', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            genero_id = request.POST.get('genero', '').strip()
            password = request.POST.get('password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()

            if not all([nombre, rut, especialidad_id, direccion, fecha_nacimiento, correo_electronico, telefono, genero_id, password, confirm_password]):
                return JsonResponse({"success": False, "message": "Todos los campos del registro son obligatorios."})

            especialidad = buscar_especialidad(especialidad_id)
            if especialidad is None:
                return JsonResponse({"success": False, "message": "Selecciona una especialidad válida."})

            if password != confirm_password:
                return JsonResponse({"success": False, "message": "Las contraseñas no coinciden."})

            if len(password) < 6:
                return JsonResponse({"success": False, "message": "La contraseña debe tener al menos 6 caracteres."})

            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validate_password(password)
            except DjangoValidationError as e:
                return JsonResponse({"success": False, "message": " | ".join(e.messages)})

            if not validar_rut_chileno(rut):
                return JsonResponse({"success": False, "message": "El RUT ingresado no es válido."})

            error_msg = usuario_existe(rut, correo_electronico)
            if error_msg:
                return JsonResponse({"success": False, "message": error_msg})

            try:
                fnac = datetime.datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
                today = datetime.date.today()
                if fnac >= today:
                    return JsonResponse({"success": False, "message": "La fecha de nacimiento no puede ser actual ni futura."})
                age = today.year - fnac.year - ((today.month, today.day) < (fnac.month, fnac.day))
                if age < 18:
                    return JsonResponse({"success": False, "message": "Debes ser mayor o igual a 18 años para registrarte como profesor."})
            except ValueError:
                return JsonResponse({"success": False, "message": "Formato de fecha inválido."})

            genero = get_object_or_404(Genero, id_genero=genero_id)

            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.create_user(
                username=rut,
                rut=rut,
                email=correo_electronico,
                rol='profesor',
                password=password,
                first_name=nombre,
                telefono=telefono,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                genero=genero
            )

            profesor = Profesor.objects.create(
                user=user,
                especialidad=especialidad
            )

            from django.contrib.auth import login as auth_login
            auth_login(request, user, backend='alumnos.backends.RutOrEmailBackend')
            abrir_sesion_rol(request, PROFESOR, profesor)

            return JsonResponse({
                "success": True,
                "message": "Profesor registrado exitosamente. Entrando al panel..."
            })
        except Exception:
            logger.exception("Error interno en regis_prof")
            return JsonResponse({"success": False, "message": "Error interno al registrar el profesor. Intenta nuevamente."}, status=500)

    generos = Genero.objects.all()
    context = {
        'generos': generos,
        'especialidades': Especialidad.objects.order_by('nombre'),
    }
    return render(request, 'user_profesor/regis_prof.html', context)


@never_cache
@profesor_required
def panel_profesor(request):
    if not request.user.is_authenticated or (getattr(request.user, 'rol', None) != 'profesor' and not hasattr(request.user, 'perfil_profesor')):
        return redirect('custom_login_alumno')

    profesor = (
        Profesor.objects.select_related('user', 'user__genero', 'especialidad')
        .filter(user=request.user)
        .first()
    )
    if not profesor:
        return redirect('custom_login_alumno')

    # Carga optimizada en memoria para evitar consultas N+1 y bucles de queries
    clases = list(
        Clase.objects.filter(profesor=profesor).select_related('asignatura', 'profesor', 'profesor__user')
    )
    inscripciones = list(
        Inscripcion.objects.filter(
            clase__profesor=profesor,
            estado__in=['confirmada', 'pendiente']
        ).select_related('alumno', 'alumno__user', 'clase', 'clase__asignatura')
    )

    inscripciones_por_clase = {}
    conteo_por_mes = {}
    for insc in inscripciones:
        inscripciones_por_clase.setdefault(insc.clase_id, []).append(insc)
        if insc.fecha_inscripcion:
            mes_num = insc.fecha_inscripcion.month
            conteo_por_mes[mes_num] = conteo_por_mes.get(mes_num, 0) + 1

    # 1. Clases del día (Máximo 6)
    clases_top6 = clases[:6]
    clases_hoy_lista = []
    inscripciones_hoy = 0
    for clase in clases_top6:
        insc_lista = inscripciones_por_clase.get(clase.id_clase, [])
        inscripciones_hoy += len(insc_lista)
        primera_insc = insc_lista[0] if insc_lista else None
        alumno_nombre = primera_insc.alumno.user.first_name if primera_insc else "Sin asignar"
        clases_hoy_lista.append({
            'nombre_curso': clase.asignatura.nombre,
            'horario': clase.horario,
            'modalidad': clase.get_modalidad_display() if hasattr(clase, 'get_modalidad_display') else clase.modalidad,
            'alumno': alumno_nombre
        })

    # 2. Métricas del Día
    # Dinero generado hoy segun las inscripciones reales de esas clases.
    inscripciones_hoy = inscripciones.filter(
        clase_id__in=[c.id_clase for c in clases[:6]]
    ).select_related('paquete')
    dinero_hoy_val = sum(paquetes.pago_profesor(_valor_clase(i)) for i in inscripciones_hoy)
    dinero_hoy = formato_clp(dinero_hoy_val)
    clases_disponibles = max(0, 8 - len(clases_hoy_lista))

    # 3. Gráfico de solicitudes mensuales (Últimos 5 meses)
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    current_month = timezone.localdate().month  # mes en Chile, no el del servidor
    rendimiento_meses = []
# Un mes sin inscripciones vale 0.
    tope_grafico = 40
    for i in range(4, -1, -1):
        month_idx = (current_month - i - 1) % 12
        month_name = meses_nombres[month_idx]
        real_count = conteo_por_mes.get(month_idx + 1, 0)
        rendimiento_meses.append({
            'mes': month_name,
            'cantidad': real_count,
            'porcentaje': min(100, int((real_count / tope_grafico) * 100))
        })

    # 4. Saldo generado y gestión de retiros
    mis_retiros = list(
        SolicitudRetiro.objects.filter(profesor=profesor)
        .select_related('banco')
        .order_by('-fecha_solicitud')
    )
    saldos = calcular_saldos(profesor, retiros_lista=mis_retiros)
    saldo_disponible = saldos['disponible']

    saldo_total_fmt = formato_clp(saldos['total_ganado'])
    saldo_disponible_fmt = formato_clp(saldo_disponible)
    saldo_pendiente_fmt = formato_clp(saldos['pendiente'])

    generos = list(Genero.objects.all())

    # S4-09: Desglose económico detallado de operaciones bajo comisión LBWUS 15%
    desgloses_profesor = list(
        DesgloseOperacion.objects.filter(profesor=profesor)
        .select_related('alumno', 'alumno__user', 'inscripcion', 'inscripcion__clase', 'inscripcion__clase__asignatura', 'plan_alumno')
        .order_by('-fecha_operacion')[:20]
    )

    context = {
        'profesor': profesor,
        'clases': clases,
        'inscripciones': inscripciones,
        'clases_hoy': clases_hoy_lista,
        'dinero_hoy': dinero_hoy,
        'clases_disponibles': clases_disponibles,
        'rendimiento_meses': rendimiento_meses,
        'saldo_total': saldo_total_fmt,
        'saldo_disponible': saldo_disponible_fmt,
        'saldo_disponible_raw': saldo_disponible,
        'saldo_pendiente': saldo_pendiente_fmt,
        'mis_retiros': mis_retiros,
        'desgloses_profesor': desgloses_profesor,
        'generos': generos,
        'especialidades': list(Especialidad.objects.order_by('nombre')),
    }
    return render(request, 'user_profesor/panel_profesor.html', context)


@profesor_required_json
def subir_titulo(request):
    if request.method != 'POST':
        return JsonResponse({"success": False, "message": "Método no permitido."})
    from . import titulo

    profesor = get_object_or_404(Profesor, id_profesor=request.session['profesor_id'])
    try:
        titulo.subir(profesor, request.FILES.get('titulo'))
    except ValidationError as e:
        return JsonResponse({"success": False, "message": e.messages[0]})
    return JsonResponse({
        "success": True,
        "message": "Título recibido. Un administrador lo revisará y te habilitará para hacer clases.",
    })


@never_cache
def foto_profesor(request, id_profesor):
    """Foto de perfil: la ve el propio profesor y, si esta habilitado, cualquier usuario con sesion.

    Misma regla que el perfil publico; sin MEDIA_URL publico.
    """
    if not request.user.is_authenticated:
        raise Http404
    profesor = get_object_or_404(Profesor.objects.select_related('user'), id_profesor=id_profesor)
    es_dueno = profesor.user_id == request.user.id
    visible = es_dueno or Profesor.objects.habilitados().filter(pk=profesor.pk).exists()
    if not (visible and profesor.user.foto_perfil):
        raise Http404
    try:
        return FileResponse(profesor.user.foto_perfil.open('rb'))
    except FileNotFoundError:
        raise Http404


@profesor_required_json
def actualizar_perfil_prof(request):
    if request.method == 'POST':
        profesor_id = request.session['profesor_id']
        profesor = get_object_or_404(Profesor.objects.select_related('user'), id_profesor=profesor_id)

        try:
            nombre = request.POST.get('nombre', '').strip()
            rut = request.POST.get('rut', '').strip()
            especialidad_id = request.POST.get('especialidad', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            correo = request.POST.get('correo_electronico', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            genero_id = request.POST.get('genero', '').strip()

            if not all([nombre, rut, especialidad_id, direccion, correo, telefono, genero_id]):
                return JsonResponse({"success": False, "message": "Todos los campos son obligatorios."})

            especialidad = buscar_especialidad(especialidad_id)
            if especialidad is None:
                return JsonResponse({"success": False, "message": "Selecciona una especialidad válida."})

            genero = get_object_or_404(Genero, id_genero=genero_id)

            if not validar_rut_chileno(rut):
                return JsonResponse({"success": False, "message": "El RUT ingresado no es válido."})

            if rut != profesor.user.rut:
                return JsonResponse({"success": False, "message": "Por motivos de seguridad, el RUT no puede ser modificado."})

            error_msg = usuario_existe(rut=rut, correo=correo, excluir_user=profesor.user)
            if error_msg:
                return JsonResponse({"success": False, "message": error_msg})

# La foto se valida antes de guardar nada: si no sirve, el perfil queda igual.
            archivo_foto = request.FILES.get('foto_perfil')
            try:
                foto_jpeg = foto.procesar(archivo_foto) if archivo_foto else None
            except ValidationError as e:
                return JsonResponse({"success": False, "message": e.messages[0]})

            # Tarifa por clase: opcional; solo afecta a los paquetes que se vendan despues.
            tarifa_txt = request.POST.get('tarifa', '').strip()
            try:
                tarifa = paquetes.validar_tarifa(tarifa_txt) if tarifa_txt else profesor.tarifa
            except ValidationError as e:
                return JsonResponse({"success": False, "message": e.messages[0]})

            profesor.user.first_name = nombre
            profesor.user.last_name = ''
            profesor.user.rut = rut
            profesor.user.username = rut
            profesor.especialidad = especialidad
            profesor.telefono_publico = request.POST.get('telefono_publico') in ('on', 'true', '1')
            profesor.tarifa = tarifa
            profesor.user.direccion = direccion
            profesor.user.email = correo
            profesor.user.telefono = telefono
            profesor.user.genero = genero
            if foto_jpeg:
                foto.guardar(profesor.user, foto_jpeg)
            profesor.user.save()
            profesor.save()

            return JsonResponse({"success": True, "message": "Tu perfil ha sido actualizado con éxito."})
        except Exception:
            logger.exception("Error interno en actualizar_perfil_prof")
            return JsonResponse({"success": False, "message": "Error interno al guardar los cambios del perfil."}, status=500)

    return JsonResponse({"success": False, "message": "Método no permitido."})


@profesor_required_json
def solicitar_retiro(request):
    profesor_id = request.session.get('profesor_id')

    if request.method == 'POST':
        from django.db import transaction

        try:
            monto_str = request.POST.get('monto', '').replace('.', '').replace('$', '').strip()
            monto = int(monto_str)
            banco = request.POST.get('banco', 'Banco Estado').strip()[:50]
            tipo_cuenta = request.POST.get('tipo_cuenta', 'Cuenta Rut / Vista').strip()[:50]
            numero_cuenta = request.POST.get('numero_cuenta', '').strip()[:30]

            if monto <= 0:
                return JsonResponse({"success": False, "message": "El monto a retirar debe ser mayor a cero."})

            with transaction.atomic():
                profesor = Profesor.objects.select_for_update().get(id_profesor=profesor_id)
                list(SolicitudRetiro.objects.select_for_update().filter(profesor=profesor))

                saldo_disponible = calcular_saldos(profesor)['disponible']

                if saldo_disponible <= 0:
                    return JsonResponse({"success": False, "message": "Aún no tienes saldo disponible para retirar."})

                if monto > saldo_disponible:
                    return JsonResponse({"success": False, "message": f"El monto ingresado excede tu saldo disponible ({formato_clp(saldo_disponible)})."})

                banco_obj, _ = Banco.objects.get_or_create(nombre=banco if banco else 'Banco Estado')
                SolicitudRetiro.objects.create(
                    profesor=profesor,
                    monto=monto,
                    banco=banco_obj,
                    tipo_cuenta=tipo_cuenta if tipo_cuenta else 'Cuenta Rut / Vista',
                    numero_cuenta=numero_cuenta
                )
            return JsonResponse({"success": True, "message": f"Solicitud de retiro por {formato_clp(monto)} registrada con éxito. Se procesará en 24 a 48 horas hábiles."})
        except ValueError:
            return JsonResponse({"success": False, "message": "Por favor ingresa un monto numérico válido."})
        except Exception:
            logger.exception("Error interno en solicitar_retiro")
            return JsonResponse({"success": False, "message": "Ocurrió un error al procesar la solicitud de retiro. Intenta nuevamente."})

    return JsonResponse({"success": False, "message": "Método no permitido."})


def _es_admin(request):
    """Solo un administrador con sesion activa (perfil Tutor) puede crear otro.

    La cuenta debe seguir activa: desactivarla no borra la sesion abierta.
    """
    return bool(request.session.get(ADMIN.clave_sesion)) and request.user.is_active


def regis_tutor(request):
    # Registro de un nuevo administrador (modelo Tutor). No es un registro publico.
    if not _es_admin(request):
        if request.method == 'POST':
            return JsonResponse(
                {
                    "success": False,
                    "message": "No tienes permiso para crear administradores.",
                },
                status=403,
            )

        return redirect('login')

    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre', '').strip()
            rut = request.POST.get('rut', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            fecha_nacimiento = request.POST.get('fecha_nacimiento', '').strip()
            correo_electronico = request.POST.get('correo_electronico', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            genero_id = request.POST.get('genero', '').strip()
            password = request.POST.get('password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()

            if not all([nombre, rut, direccion, fecha_nacimiento, correo_electronico, telefono, genero_id, password, confirm_password]):
                return JsonResponse({"success": False, "message": "Todos los campos son obligatorios para registrarse."})

            if password != confirm_password:
                return JsonResponse({"success": False, "message": "Las contraseñas no coinciden."})

            if len(password) < 6:
                return JsonResponse({"success": False, "message": "La contraseña debe tener al menos 6 caracteres."})

            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validate_password(password)
            except DjangoValidationError as e:
                return JsonResponse({"success": False, "message": " | ".join(e.messages)})

            if not validar_rut_chileno(rut):
                return JsonResponse({"success": False, "message": "El RUT ingresado no es válido."})

            error_msg = usuario_existe(rut, correo_electronico)
            if error_msg:
                return JsonResponse({"success": False, "message": error_msg})

            try:
                fnac = datetime.datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
                today = datetime.date.today()
                if fnac >= today:
                    return JsonResponse({"success": False, "message": "La fecha de nacimiento no puede ser actual ni futura."})
                age = today.year - fnac.year - ((today.month, today.day) < (fnac.month, fnac.day))
                if age < 18:
                    return JsonResponse({"success": False, "message": "Debes ser mayor o igual a 18 años para registrarte como administrador."})
            except ValueError:
                return JsonResponse({"success": False, "message": "Formato de fecha inválido."})

            genero = get_object_or_404(Genero, id_genero=genero_id)

            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.create_user(
                username=rut,
                rut=rut,
                email=correo_electronico,
                rol='admin',
                password=password,
                first_name=nombre,
                telefono=telefono,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                genero=genero
            )
            user.save()

            tutor = Tutor.objects.create(user=user)

            from django.contrib.auth import login as auth_login
            auth_login(request, user, backend='alumnos.backends.RutOrEmailBackend')
            abrir_sesion_rol(request, ADMIN, tutor)

            return JsonResponse({
                "success": True,
                "message": "Administrador registrado exitosamente. Ingresando al panel..."
            })
        except Exception:
            logger.exception("Error interno en regis_tutor")
            return JsonResponse({"success": False, "message": "Error interno al registrar el administrador."}, status=500)

    generos = Genero.objects.all()
    context = {'generos': generos}
    return render(request, 'user_profesor/regis_tutor.html', context)


from django.contrib.auth import logout as auth_logout


@never_cache
@require_POST
def logout_prof(request):
    auth_logout(request)
    request.session.flush()
    return redirect('home')
