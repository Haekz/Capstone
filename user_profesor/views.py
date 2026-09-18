from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from alumnos.models import Genero, Profesor, Clase, Inscripcion, Tutor

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

            from django.contrib.auth.hashers import make_password
            # Crear el registro del Profesor
            profesor = Profesor.objects.create(
                nombre=nombre,
                rut=rut,
                especialidad=especialidad,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero,
                password=make_password(password)
            )

            # Iniciar sesión automáticamente (guardar ID en la sesión)
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

        # Buscar profesor por Correo Electrónico o por RUT
        profesor = Profesor.objects.filter(correo_electronico__iexact=identificador).first()
        if not profesor:
            profesor = Profesor.objects.filter(rut__iexact=identificador).first()

        from django.contrib.auth.hashers import check_password
        if profesor and profesor.password and check_password(password, profesor.password):
            # Guardar ID en la sesión
            request.session['profesor_id'] = profesor.id_profesor
            return JsonResponse({
                "success": True, 
                "message": f"Bienvenido de vuelta, Prof. {profesor.nombre}."
            })
        else:
            return JsonResponse({
                "success": False, 
                "message": "Credenciales inválidas. Por favor verifique sus datos."
            })

    return redirect('regis_prof')


def panel_profesor(request):
    import datetime
    profesor_id = request.session.get('profesor_id')
    if not profesor_id:
        return redirect('regis_prof')

    profesor = get_object_or_404(Profesor, id_profesor=profesor_id)
    clases = Clase.objects.filter(id_profesor=profesor)
    inscripciones = Inscripcion.objects.filter(id_clase__id_profesor=profesor)

    # 1. Clases del día (Máximo 6)
    clases_hoy_lista = []
    for clase in clases[:6]:
        # Buscar primer alumno inscrito
        insc = inscripciones.filter(id_clase=clase).first()
        alumno_nombre = insc.id_alumno.nombre if insc else "Sin asignar"
        clases_hoy_lista.append({
            'nombre_curso': clase.nombre_curso,
            'horario': clase.horario,
            'modalidad': clase.get_modalidad_display() if hasattr(clase, 'get_modalidad_display') else clase.modalidad,
            'alumno': alumno_nombre
        })

    # 2. Métricas del Día
    # Dinero generado hoy ($15.000 por clase activa asignada)
    dinero_hoy_val = len(clases_hoy_lista) * 15000
    dinero_hoy = f"${dinero_hoy_val:,}".replace(",", ".")
    # Contador de clases disponibles diarias (base 8 máximo diario)
    clases_disponibles = max(0, 8 - len(clases_hoy_lista))

    # 3. Gráfico de solicitudes mensuales (Últimos 5 meses)
    meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    current_month = datetime.datetime.now().month
    rendimiento_meses = []
    
    # Generar últimos 5 meses
    mock_values = [14, 22, 18, 25, 32]
    for i in range(4, -1, -1):
        month_idx = (current_month - i - 1) % 12
        month_name = meses_nombres[month_idx]
        real_count = inscripciones.filter(fecha_inscripcion__month=(month_idx + 1)).count()
        display_count = real_count if real_count > 0 else mock_values[4 - i]
        
        rendimiento_meses.append({
            'mes': month_name,
            'cantidad': display_count,
            'porcentaje': min(100, int((display_count / 40) * 100))
        })

    # 4. Saldo generado y gestión de retiros
    from alumnos.models import SolicitudRetiro
    from django.db.models import Sum

    total_inscripciones = inscripciones.count()
    saldo_total_ganado = total_inscripciones * 15000 if total_inscripciones > 0 else 45000
    saldo_profe_base = total_inscripciones * 12000 if total_inscripciones > 0 else 36000

    retiros_aprobados = SolicitudRetiro.objects.filter(id_profesor=profesor, estado='aprobado').aggregate(Sum('monto'))['monto__sum'] or 0
    retiros_pendientes = SolicitudRetiro.objects.filter(id_profesor=profesor, estado='pendiente').aggregate(Sum('monto'))['monto__sum'] or 0

    saldo_disponible = max(0, saldo_profe_base - retiros_aprobados - retiros_pendientes)
    saldo_pendiente = (saldo_total_ganado - saldo_profe_base) + retiros_pendientes

    saldo_total_fmt = f"${saldo_total_ganado:,}".replace(",", ".")
    saldo_disponible_fmt = f"${saldo_disponible:,}".replace(",", ".")
    saldo_pendiente_fmt = f"${saldo_pendiente:,}".replace(",", ".")

    mis_retiros = SolicitudRetiro.objects.filter(id_profesor=profesor).order_by('-fecha_solicitud')
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
            
            profesor.nombre = nombre
            profesor.rut = rut
            profesor.especialidad = especialidad
            profesor.direccion = direccion
            profesor.correo_electronico = correo
            profesor.telefono = telefono
            profesor.genero = genero
            profesor.save()
            
            return JsonResponse({"success": True, "message": "Tu perfil ha sido actualizado con éxito."})
        except Exception as e:
            return JsonResponse({"success": False, "message": f"Error al guardar los cambios: {str(e)}"})
            
    return JsonResponse({"success": False, "message": "Método no permitido."})


def logout_prof(request):
    # Eliminar la sesión del profesor
    if 'profesor_id' in request.session:
        del request.session['profesor_id']
    return redirect('home')


def solicitar_retiro(request):
    profesor_id = request.session.get('profesor_id')
    if not profesor_id:
        return JsonResponse({"success": False, "message": "Sesión inválida."})

    if request.method == 'POST':
        profesor = get_object_or_404(Profesor, id_profesor=profesor_id)
        from alumnos.models import SolicitudRetiro, Inscripcion
        from django.db.models import Sum

        try:
            monto_str = request.POST.get('monto', '').replace('.', '').replace('$', '').strip()
            monto = int(monto_str)
            banco = request.POST.get('banco', 'Banco Estado').strip()
            tipo_cuenta = request.POST.get('tipo_cuenta', 'Cuenta Rut / Vista').strip()
            numero_cuenta = request.POST.get('numero_cuenta', '').strip()

            if monto <= 0:
                return JsonResponse({"success": False, "message": "El monto a retirar debe ser mayor a cero."})

            # Validar saldo disponible
            inscripciones_count = Inscripcion.objects.filter(id_clase__id_profesor=profesor).count()
            saldo_profe_base = inscripciones_count * 12000 if inscripciones_count > 0 else 36000
            retiros_aprobados = SolicitudRetiro.objects.filter(id_profesor=profesor, estado='aprobado').aggregate(Sum('monto'))['monto__sum'] or 0
            retiros_pendientes = SolicitudRetiro.objects.filter(id_profesor=profesor, estado='pendiente').aggregate(Sum('monto'))['monto__sum'] or 0
            saldo_disponible = max(0, saldo_profe_base - retiros_aprobados - retiros_pendientes)

            if monto > saldo_disponible:
                return JsonResponse({"success": False, "message": f"El monto ingresado excede tu saldo disponible (${saldo_disponible:,}).".replace(",", ".")})

            SolicitudRetiro.objects.create(
                id_profesor=profesor,
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


def regis_tutor(request):
    # esta parte es de registrar un nuevo administrador usando el modelo Tutor
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

            from django.contrib.auth.hashers import make_password
            tutor = Tutor.objects.create(
                nombre=nombre,
                rut=rut,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero,
                password=make_password(password)
            )

            # esta parte es de guardar la sesión de administrador
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
    # esta parte es del acceso rápido sin contraseña para administradores
    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        
        if not identificador:
            return JsonResponse({"success": False, "message": "Por favor ingrese su RUT o Correo Electrónico."})

        # esta parte es de buscar al admin por correo o rut
        tutor = Tutor.objects.filter(correo_electronico=identificador).first()
        if not tutor:
            tutor = Tutor.objects.filter(rut=identificador).first()

        if tutor:
            request.session['admin_id'] = tutor.id_tutor
            return JsonResponse({
                "success": True, 
                "message": f"Bienvenido de vuelta, Administrador {tutor.nombre}."
            })
        else:
            return JsonResponse({
                "success": False, 
                "message": "No se encontró ningún administrador registrado con esos datos. Es obligatorio registrarse primero."
            })

    return redirect('regis_tutor')


