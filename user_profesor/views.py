import datetime
import logging
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from alumnos.models import (
    Especialidad, Genero, Profesor, Clase, Inscripcion, Tutor, CuentaBancaria, TIPOS_CUENTA, SolicitudRetiro, Banco,
)
from alumnos.decorators import profesor_required, profesor_required_json
from alumnos.roles import ADMIN, PROFESOR, abrir_sesion_rol
from alumnos.utils import formato_clp, validar_rut_chileno, usuario_existe
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.views.decorators.http import require_POST
from . import cambio_cuenta, foto
from alumnos import catalogos, liquidacion, paquetes
from agenda import panel as agenda_panel
from observaciones import panel as observaciones_panel
from mensajes import panel as mensajes_panel

logger = logging.getLogger(__name__)



def calcular_saldos(profesor):
    """Devuelve los saldos de un profesor a partir de sus inscripciones.

    Sin inscripciones el resultado es 0: una cuenta nueva no tiene dinero.
    Solo cuentan las clases ya dictadas: una reserva futura todavia se puede
    cancelar, y lo no realizado no se liquida (docs/POLITICA_PAQUETES.md, punto 10).
    Excepcion: si el alumno cancela con menos de 4 h, la clase se le paga igual (02-nov).
    """
    from django.db.models import Sum

    from alumnos.models import SolicitudRetiro

    inscripciones = Inscripcion.objects.filter(clase__profesor=profesor).pagables().select_related('paquete')
    valores = [paquetes.valor_clase(i) for i in inscripciones]

    total_ganado = sum(valores)
    corresponde_al_profesor = sum(paquetes.pago_profesor(v) for v in valores)

    retiros = SolicitudRetiro.objects.filter(profesor=profesor)
    aprobados = retiros.filter(
        estado__in=[SolicitudRetiro.APROBADO, SolicitudRetiro.PAGADO]
    ).aggregate(Sum('monto'))['monto__sum'] or 0
    pendientes = retiros.filter(estado=SolicitudRetiro.PENDIENTE).aggregate(Sum('monto'))['monto__sum'] or 0

    disponible = max(0, corresponde_al_profesor - aprobados - pendientes)
    # La comision de la plataforma mas lo que aun esta en tramite.
    pendiente = (total_ganado - corresponde_al_profesor) + pendientes

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

            from alumnos.utils import validar_clave_nueva
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validar_clave_nueva(password, rut, correo_electronico)
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
    dinero_hoy_val = sum(paquetes.pago_profesor(paquetes.valor_clase(i)) for i in inscripciones_hoy)
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
        'cuenta_bancaria': CuentaBancaria.objects.filter(profesor=profesor).first(),
        'bancos': catalogos.BANCOS,
        'tipos_cuenta': TIPOS_CUENTA,
        'minimo_retiro': formato_clp(liquidacion.MINIMO),
        'minimo_retiro_raw': liquidacion.MINIMO,
        'proximo_pago': liquidacion.proximo_pago(profesor, timezone.localdate()),
        'frecuencia_vigente': liquidacion.frecuencia_vigente(profesor, timezone.localdate()),
        'frecuencias': liquidacion.FRECUENCIAS,
        'generos': generos,
        'especialidades': Especialidad.objects.order_by('nombre'),
        **agenda_panel.contexto(profesor),  # seccion Mi Agenda (agenda/panel.py)
        **observaciones_panel.contexto_profesor(profesor),  # sus clases realizadas, en la misma seccion
        **mensajes_panel.contexto_profesor(profesor, request.GET.get('c')),  # Buzon (mensajes/panel.py)
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
        "message": "Título recibido. Nuestro equipo de soporte lo revisará y te habilitará para hacer clases.",
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
                return JsonResponse({"success": False, "message": e.messages[0]}, status=400)

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
@require_POST
def guardar_cuenta_bancaria(request):
    """Registra la cuenta donde se le paga al profesor (titular: su propio RUT).

    La primera se guarda al tiro; cambiarla exige la contrasena y el enlace del correo.
    """
    profesor_id = request.session.get('profesor_id')
    actual = CuentaBancaria.objects.select_related('profesor__user').filter(profesor_id=profesor_id).first()
    cuenta = CuentaBancaria(profesor_id=profesor_id)
    cuenta.banco = request.POST.get('banco', '')
    cuenta.tipo_cuenta = request.POST.get('tipo_cuenta', '')
    try:
        cuenta.asignar_numero(request.POST.get('numero_cuenta'))
        cuenta.full_clean(exclude=['profesor'])  # valida banco y tipo contra las listas cerradas
    except ValidationError as e:
        return JsonResponse({"success": False, "message": e.messages[0]})
    if actual is None:
        cuenta.save()
        return JsonResponse({"success": True, "message": f"Cuenta guardada: {cuenta.banco} {cuenta.enmascarado}."})
    if not request.user.check_password(request.POST.get('password', '')):
        return JsonResponse({"success": False, "message": "La contraseña no es correcta."})
    if not cambio_cuenta.pedir(request, actual, cuenta):
        return JsonResponse({"success": False, "message": "No pudimos enviar el correo de confirmación. Intenta más tarde."})
    return JsonResponse({"success": True, "message": "Te enviamos un enlace a tu correo para confirmar el cambio. Vence en 24 horas."})


@profesor_required
def confirmar_cambio_cuenta(request, token):
    try:
        cuenta = cambio_cuenta.confirmar(request.session.get('profesor_id'), token)
    except ValidationError as e:
        messages.error(request, e.messages[0])
    else:
        desde = timezone.localtime(cuenta.pagable_desde).strftime('%d/%m/%Y %H:%M')
        messages.success(request, f'Cuenta cambiada a {cuenta.banco} {cuenta.enmascarado}. '
                                  f'Por seguridad, los pagos a esta cuenta se habilitan el {desde}.')
    return redirect('panel_profesor')


# _json: el panel llama esta vista con fetch y espera {'success': ...};
# un redirect le romperia el res.json().
@profesor_required_json
@require_POST
def guardar_frecuencia_pago(request):
    """Semanal o mensual; el cambio rige desde el ciclo siguiente (F4)."""
    profesor = Profesor.objects.get(id_profesor=request.session.get('profesor_id'))
    try:
        desde = liquidacion.cambiar_frecuencia(profesor, request.POST.get('frecuencia', ''), timezone.localdate())
    except ValidationError as e:
        return JsonResponse({"success": False, "message": e.messages[0]})
    if desde is None:
        return JsonResponse({"success": True, "message": f"Sigues con pago {profesor.get_frecuencia_pago_display().lower()}."})
    return JsonResponse({"success": True, "message": f"Desde el {desde:%d/%m/%Y} tu pago será "
                                                    f"{profesor.get_frecuencia_nueva_display().lower()}. El ciclo en curso no cambia."})


# _json: el panel llama esta vista con fetch y espera {'success': ...};
# un redirect le romperia el res.json().
@profesor_required_json
def solicitar_retiro(request):
    profesor_id = request.session.get('profesor_id')

    if request.method == 'POST':
        from django.db import transaction

        try:
            monto_str = request.POST.get('monto', '').replace('.', '').replace('$', '').strip()
            monto = int(monto_str)

            if monto < liquidacion.MINIMO:
                return JsonResponse({"success": False, "message": f"El mínimo para retirar es {formato_clp(liquidacion.MINIMO)}. Tu saldo se acumula hasta alcanzarlo."})

            cuenta = CuentaBancaria.objects.filter(profesor_id=profesor_id).first()
            if cuenta is None:
                return JsonResponse({"success": False, "message": "Registra tu cuenta bancaria antes de solicitar un retiro."})

            with transaction.atomic():
                profesor = Profesor.objects.select_for_update().get(id_profesor=profesor_id)
                list(SolicitudRetiro.objects.select_for_update().filter(profesor=profesor))

                saldo_disponible = calcular_saldos(profesor)['disponible']

                if saldo_disponible <= 0:
                    return JsonResponse({"success": False, "message": "Aún no tienes saldo disponible para retirar."})

                if monto > saldo_disponible:
                    return JsonResponse({"success": False, "message": f"El monto ingresado excede tu saldo disponible ({formato_clp(saldo_disponible)})."})

                # Copia enmascarada: el numero completo solo vive cifrado en la cuenta.
                retiro = SolicitudRetiro.objects.create(
                    profesor=profesor,
                    monto=monto,
                    banco=Banco.objects.get_or_create(nombre=cuenta.banco)[0],
                    tipo_cuenta=cuenta.tipo_cuenta,
                    numero_cuenta=cuenta.enmascarado,
                    pagar_el=liquidacion.proximo_pago(profesor, timezone.localdate()),
                )
            return JsonResponse({"success": True, "message": f"Solicitud de retiro por {formato_clp(monto)} registrada. Se paga el {retiro.pagar_el:%d/%m/%Y}."})
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

            from alumnos.utils import validar_clave_nueva
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validar_clave_nueva(password, rut, correo_electronico)
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
