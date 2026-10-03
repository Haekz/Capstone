from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from alumnos.models import Genero, Profesor, Clase, Inscripcion, Tutor

# Tarifas por inscripcion real. Antes estaban escritas a mano dentro de cada
# vista, junto a un saldo de regalo para las cuentas sin actividad.
VALOR_INSCRIPCION = 15000   # lo que paga el alumno
PAGO_PROFESOR = 12000       # lo que le corresponde al profesor


def calcular_saldos(profesor):
    """Devuelve los saldos de un profesor a partir de sus inscripciones.

    Sin inscripciones el resultado es 0: una cuenta nueva no tiene dinero.
    Antes se devolvian 45000/36000 de relleno y el profesor podia pedir un
    retiro por plata que nunca existio.
    """
    from django.db.models import Sum

    from alumnos.models import SolicitudRetiro

    inscripciones = Inscripcion.objects.filter(clase__profesor=profesor).count()

    total_ganado = inscripciones * VALOR_INSCRIPCION
    corresponde_al_profesor = inscripciones * PAGO_PROFESOR

    retiros = SolicitudRetiro.objects.filter(profesor=profesor)
    aprobados = retiros.filter(estado='aprobado').aggregate(Sum('monto'))['monto__sum'] or 0
    pendientes = retiros.filter(estado='pendiente').aggregate(Sum('monto'))['monto__sum'] or 0

    disponible = max(0, corresponde_al_profesor - aprobados - pendientes)
    # La comision de la plataforma mas lo que aun esta en tramite.
    pendiente = (total_ganado - corresponde_al_profesor) + pendientes

    return {
        'total_ganado': total_ganado,
        'disponible': disponible,
        'pendiente': pendiente,
    }


def formato_clp(monto):
    """12345 -> '$12.345'."""
    return f"${monto:,}".replace(",", ".")


# --- Vistas de Registro y Acceso de Profesor ---

def regis_prof(request):
    if request.method == 'POST':
        try:
            nombre = request.POST.get('nombre', '').strip()
            rut = request.POST.get('rut', '').strip()
            especialidad = request.POST.get('especialidad', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            fecha_nacimiento = request.POST.get('fecha_nacimiento', '').strip()
            correo_electronico = request.POST.get('correo_electronico', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            genero_id = request.POST.get('genero', '').strip()
            password = request.POST.get('password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()

            # Validar que todos los campos obligatorios estén presentes
            if not all([nombre, rut, especialidad, direccion, fecha_nacimiento, correo_electronico, telefono, genero_id, password, confirm_password]):
                return JsonResponse({"success": False, "message": "Todos los campos del registro son obligatorios."})

            if password != confirm_password:
                return JsonResponse({"success": False, "message": "Las contraseñas no coinciden."})

            if len(password) < 6:
                return JsonResponse({"success": False, "message": "La contraseña debe tener al menos 6 caracteres."})

            from alumnos.utils import validar_rut_chileno, usuario_existe
            from datetime import datetime, date

            if not validar_rut_chileno(rut):
                return JsonResponse({"success": False, "message": "El RUT ingresado no es válido."})

            error_msg = usuario_existe(rut, correo_electronico)
            if error_msg:
                return JsonResponse({"success": False, "message": error_msg})

            try:
                fnac = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
                today = date.today()
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
            # Crear usuario CustomUser centralizado
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

            # Crear el registro del Profesor vinculado al User
            profesor = Profesor.objects.create(
                user=user,
                nombre=nombre,
                rut=rut,
                especialidad=especialidad,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero
            )

            # Iniciar sesión automáticamente
            from django.contrib.auth import login as auth_login
            auth_login(request, user, backend='alumnos.backends.RutOrEmailBackend')
            request.session['profesor_id'] = profesor.id_profesor

            return JsonResponse({
                "success": True,
                "message": "Profesor registrado exitosamente. Entrando al panel..."
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Error al registrar: {str(e)}"})

    generos = Genero.objects.all()
    context = {'generos': generos}
    return render(request, 'user_profesor/regis_prof.html', context)


def login_prof(request):
    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        password = request.POST.get('password', '').strip()

        if not identificador or not password:
            return JsonResponse({"success": False, "message": "Por favor ingrese todos los campos."})

        from django.contrib.auth import authenticate, login as auth_login
        user = authenticate(request, username=identificador, password=password)
        if user and (getattr(user, 'rol', None) == 'profesor' or hasattr(user, 'perfil_profesor')):
            auth_login(request, user)
            prof_id = user.perfil_profesor.id_profesor if hasattr(user, 'perfil_profesor') else user.id
            request.session['profesor_id'] = prof_id
            nombre_prof = user.perfil_profesor.user.first_name if hasattr(user, 'perfil_profesor') else (user.first_name or user.username)
            return JsonResponse({
                "success": True, 
                "message": f"Bienvenido de vuelta, Prof. {nombre_prof}."
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "Credenciales inválidas o no tienes cuenta de profesor."
            })

    return redirect('regis_prof')


@never_cache
def panel_profesor(request):
    import datetime
    profesor_id = request.session.get('profesor_id')
    if not profesor_id:
        return redirect('regis_prof')

    profesor = get_object_or_404(Profesor, id_profesor=profesor_id)
    clases = Clase.objects.filter(profesor=profesor)
    inscripciones = Inscripcion.objects.filter(clase__profesor=profesor)

    # 1. Clases del día (Máximo 6)
    clases_hoy_lista = []
    for clase in clases[:6]:
        # Buscar primer alumno inscrito
        insc = inscripciones.filter(clase=clase).first()
        alumno_nombre = insc.alumno.user.first_name if insc else "Sin asignar"
        clases_hoy_lista.append({
            'nombre_curso': clase.nombre_curso,
            'horario': clase.horario,
            'modalidad': clase.get_modalidad_display() if hasattr(clase, 'get_modalidad_display') else clase.modalidad,
            'alumno': alumno_nombre
        })

    # 2. Métricas del Día
    # Dinero generado hoy segun las inscripciones reales de esas clases.
    inscripciones_hoy = inscripciones.filter(
        clase_id__in=[c.id_clase for c in clases[:6]]
    ).count()
    dinero_hoy_val = inscripciones_hoy * PAGO_PROFESOR
    dinero_hoy = formato_clp(dinero_hoy_val)
    # Contador de clases disponibles diarias (base 8 máximo diario)
    clases_disponibles = max(0, 8 - len(clases_hoy_lista))

    # 3. Gráfico de solicitudes mensuales (Últimos 5 meses)
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    current_month = datetime.datetime.now().month
    rendimiento_meses = []

    # Un mes sin inscripciones vale 0. Antes se rellenaba con mock_values y el
    # grafico mostraba actividad inventada.
    tope_grafico = 40
    for i in range(4, -1, -1):
        month_idx = (current_month - i - 1) % 12
        month_name = meses_nombres[month_idx]
        real_count = inscripciones.filter(fecha_inscripcion__month=(month_idx + 1)).count()

        rendimiento_meses.append({
            'mes': month_name,
            'cantidad': real_count,
            'porcentaje': min(100, int((real_count / tope_grafico) * 100))
        })

    # 4. Saldo generado y gestión de retiros
    from alumnos.models import SolicitudRetiro

    saldos = calcular_saldos(profesor)
    saldo_disponible = saldos['disponible']

    saldo_total_fmt = formato_clp(saldos['total_ganado'])
    saldo_disponible_fmt = formato_clp(saldo_disponible)
    saldo_pendiente_fmt = formato_clp(saldos['pendiente'])

    mis_retiros = SolicitudRetiro.objects.filter(profesor=profesor).order_by('-fecha_solicitud')
    generos = Genero.objects.all()

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
        'generos': generos,
    }
    return render(request, 'user_profesor/panel_profesor.html', context)


def actualizar_perfil_prof(request):
    if request.method == 'POST':
        profesor_id = request.session.get('profesor_id')
        if not profesor_id:
            return JsonResponse({"success": False, "message": "Sesión inválida."})

        profesor = get_object_or_404(Profesor, id_profesor=profesor_id)

        try:
            nombre = request.POST.get('nombre', '').strip()
            rut = request.POST.get('rut', '').strip()
            especialidad = request.POST.get('especialidad', '').strip()
            direccion = request.POST.get('direccion', '').strip()
            correo = request.POST.get('correo_electronico', '').strip()
            telefono = request.POST.get('telefono', '').strip()
            genero_id = request.POST.get('genero', '').strip()

            if not all([nombre, rut, especialidad, direccion, correo, telefono, genero_id]):
                return JsonResponse({"success": False, "message": "Todos los campos son obligatorios."})

            genero = get_object_or_404(Genero, id_genero=genero_id)

            profesor.user.first_name = nombre
            profesor.user.rut = rut
            profesor.especialidad = especialidad
            profesor.user.direccion = direccion
            profesor.user.email = correo
            profesor.user.telefono = telefono
            profesor.user.genero = genero
            profesor.save()

            return JsonResponse({"success": True, "message": "Tu perfil ha sido actualizado con éxito."})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Error al guardar los cambios: {str(e)}"})

    return JsonResponse({"success": False, "message": "Método no permitido."})


def logout_prof(request):
    from django.contrib.auth import logout as auth_logout
    auth_logout(request)
    if 'profesor_id' in request.session:
        del request.session['profesor_id']
    return redirect('home')


def solicitar_retiro(request):
    profesor_id = request.session.get('profesor_id')
    if not profesor_id:
        return JsonResponse({"success": False, "message": "Sesión inválida."})

    if request.method == 'POST':
        profesor = get_object_or_404(Profesor, id_profesor=profesor_id)
        from alumnos.models import SolicitudRetiro

        try:
            monto_str = request.POST.get('monto', '').replace('.', '').replace('$', '').strip()
            monto = int(monto_str)
            banco = request.POST.get('banco', 'Banco Estado').strip()
            tipo_cuenta = request.POST.get('tipo_cuenta', 'Cuenta Rut / Vista').strip()
            numero_cuenta = request.POST.get('numero_cuenta', '').strip()

            if monto <= 0:
                return JsonResponse({"success": False, "message": "El monto a retirar debe ser mayor a cero."})

            # Validar saldo disponible con la misma regla que muestra el panel.
            saldo_disponible = calcular_saldos(profesor)['disponible']

            if saldo_disponible <= 0:
                return JsonResponse({"success": False, "message": "Aún no tienes saldo disponible para retirar."})

            if monto > saldo_disponible:
                return JsonResponse({"success": False, "message": f"El monto ingresado excede tu saldo disponible ({formato_clp(saldo_disponible)})."})

            SolicitudRetiro.objects.create(
                profesor=profesor,
                monto=monto,
                banco=banco if banco else 'Banco Estado',
                tipo_cuenta=tipo_cuenta if tipo_cuenta else 'Cuenta Rut / Vista',
                numero_cuenta=numero_cuenta
            )
            return JsonResponse({"success": True, "message": f"Solicitud de retiro por ${monto:,} registrada con éxito. Se procesará en 24 a 48 horas hábiles.".replace(",", ".")})
        except ValueError:
            return JsonResponse({"success": False, "message": "Por favor ingresa un monto numérico válido."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    return JsonResponse({"success": False, "message": "Método no permitido."})


def _es_admin(request):
    """Solo un administrador con sesion activa puede crear otro.

    Se acepta la clave de sesion 'admin_id' (que es como login_admin() marca
    la sesion) o el flag is_staff/is_superuser de un usuario de Django.
    """
    if request.session.get('admin_id'):
        return True

    user = getattr(request, 'user', None)

    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def regis_tutor(request):
    # esta parte es de registrar un nuevo administrador usando el modelo Tutor.
    # NO es un registro publico: crear administradores desde internet permitia
    # que cualquiera se diera acceso al portal y al /admin/ de Django.
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

            from alumnos.utils import validar_rut_chileno, usuario_existe
            from datetime import datetime, date

            if not validar_rut_chileno(rut):
                return JsonResponse({"success": False, "message": "El RUT ingresado no es válido."})

            error_msg = usuario_existe(rut, correo_electronico)
            if error_msg:
                return JsonResponse({"success": False, "message": error_msg})

            try:
                fnac = datetime.strptime(fecha_nacimiento, '%Y-%m-%d').date()
                today = date.today()
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
            # Sin is_staff: el acceso al portal lo da el perfil Tutor, no el
            # flag de Django. is_staff abre /admin/, que es otra cosa y debe
            # concederse a mano desde la consola.
            user.save()

            tutor = Tutor.objects.create(
                user=user,
                nombre=nombre,
                rut=rut,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero
            )

            # Iniciar sesión de administrador
            from django.contrib.auth import login as auth_login
            auth_login(request, user, backend='alumnos.backends.RutOrEmailBackend')
            request.session['admin_id'] = tutor.id_tutor

            return JsonResponse({
                "success": True,
                "message": "Administrador registrado exitosamente. Ingresando al panel..."
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Error al registrar: {str(e)}"})

    generos = Genero.objects.all()
    context = {'generos': generos}
    return render(request, 'user_profesor/regis_tutor.html', context)


def login_admin(request):
    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        password = request.POST.get('password', '').strip()

        if not identificador or not password:
            return JsonResponse({"success": False, "message": "Por favor ingrese RUT/Correo y contraseña."})

        from django.contrib.auth import authenticate, login as auth_login
        user = authenticate(request, username=identificador, password=password)
        if user and (getattr(user, 'rol', None) == 'admin' or hasattr(user, 'perfil_tutor') or user.is_staff or user.is_superuser):
            auth_login(request, user)
            tutor = getattr(user, 'perfil_tutor', None) or Tutor.objects.filter(user=user).first()
            admin_id = tutor.id_tutor if tutor else user.id
            request.session['admin_id'] = admin_id
            nombre_mostrar = tutor.user.first_name if tutor else (user.first_name or user.username)
            return JsonResponse({
                "success": True,
                "message": f"Bienvenido de vuelta, Administrador {nombre_mostrar}."
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "Credenciales inválidas o no tienes permisos de administrador."
            })

    return redirect('login')


