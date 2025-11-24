from datetime import datetime, timedelta, time

from django import forms
from django.contrib import messages
from django.contrib.auth import logout as django_logout
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from Controllers.forms import LoginForm, RegistroForm
from Controllers.reserva_forms import ReservaForm
from Models.models import Cliente, Insumo, Reserva, Servicio, Vehiculo


# -----------------------
# Utilidades internas
# -----------------------

def _require_admin(request):
    """Valida que el usuario autenticado sea administrador y devuelve el objeto Cliente."""
    cliente_id = request.session.get('cliente_id')
    if not cliente_id:
        return None, redirect('login')

    usuario = get_object_or_404(Cliente, pk=cliente_id)
    if not usuario.es_admin:
        messages.error(request, 'Acceso restringido solo para administradores.')
        return None, redirect('home')

    return usuario, None


def _set_cliente_session(request, cliente):
    request.session['cliente_id'] = cliente.cliente_id
    request.session['nombre_cliente'] = cliente.nombre_cliente
    request.session['apellido_cliente'] = cliente.apellido_cliente
    request.session['es_admin'] = cliente.es_admin


def _clear_cliente_session(request):
    for key in ['cliente_id', 'nombre_cliente', 'apellido_cliente', 'es_admin']:
        request.session.pop(key, None)


# -----------------------
# Vistas de administración
# -----------------------

def admin_insumo_nuevo(request):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    class InsumoForm(forms.ModelForm):
        class Meta:
            model = Insumo
            fields = ['nombre', 'descripcion', 'cantidad', 'unidad_medida', 'precio_unitario']

    if request.method == 'POST':
        form = InsumoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Insumo creado correctamente.')
            return redirect('admin_inventario')
    else:
        form = InsumoForm()

    return render(
        request,
        'admin/admin_insumo_form.html',
        {
            'form': form,
            'accion': 'Nuevo',
            'admin_usuario': usuario,
        },
    )


def admin_insumo_editar(request, id):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    insumo = get_object_or_404(Insumo, pk=id)

    class InsumoForm(forms.ModelForm):
        class Meta:
            model = Insumo
            fields = ['nombre', 'descripcion', 'cantidad', 'unidad_medida', 'precio_unitario']

    if request.method == 'POST':
        form = InsumoForm(request.POST, instance=insumo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Insumo actualizado correctamente.')
            return redirect('admin_inventario')
    else:
        form = InsumoForm(instance=insumo)

    return render(
        request,
        'admin/admin_insumo_form.html',
        {
            'form': form,
            'accion': 'Editar',
            'admin_usuario': usuario,
        },
    )


def admin_insumo_eliminar(request, id):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    insumo = get_object_or_404(Insumo, pk=id)
    if request.method == 'POST':
        insumo.delete()
        messages.success(request, 'Insumo eliminado correctamente.')
        return redirect('admin_inventario')

    return render(
        request,
        'admin/admin_insumo_eliminar.html',
        {
            'insumo': insumo,
            'admin_usuario': usuario,
        },
    )


def admin_inventario(request):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    insumos = Insumo.objects.all().order_by('nombre')
    return render(
        request,
        'admin/admin_inventario.html',
        {
            'insumos': insumos,
            'admin_usuario': usuario,
        },
    )


def admin_dashboard(request):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    filtro_estado = request.GET.get('estado', '')
    reservas = Reserva.objects.all().select_related('usuario', 'vehiculo', 'servicio')
    if filtro_estado:
        reservas = reservas.filter(estado_reserva=filtro_estado)

    hoy = timezone.now()
    reservas_mes = Reserva.objects.filter(
        fecha_hora_inicio__year=hoy.year,
        fecha_hora_inicio__month=hoy.month,
    )
    total_reservas_mes = reservas_mes.count()
    ingresos_estimados_mes = sum([r.servicio.duracion_servicio * 10 for r in reservas_mes])

    insumo_obj = Insumo.objects.order_by('-cantidad').first()
    insumo_mas_usado = insumo_obj.nombre if insumo_obj else '-'

    if reservas_mes.exists():
        fecha_limite = reservas_mes.earliest('fecha_hora_inicio').fecha_hora_inicio
    else:
        fecha_limite = hoy

    patentes_mes = set(reservas_mes.values_list('patente', flat=True))
    patentes_anteriores = set(
        Reserva.objects.filter(fecha_hora_inicio__lt=fecha_limite).values_list('patente', flat=True)
    )
    patentes_nuevas = patentes_mes - patentes_anteriores
    total_clientes_nuevos = len(patentes_nuevas)
    total_clientes_antiguos = len(patentes_mes & patentes_anteriores)

    pastel_clientes = {
        'nuevos': total_clientes_nuevos,
        'antiguos': total_clientes_antiguos,
    }

    contexto = {
        'reservas': reservas,
        'filtro_estado': filtro_estado,
        'total_reservas_mes': total_reservas_mes,
        'ingresos_estimados_mes': ingresos_estimados_mes,
        'insumo_mas_usado': insumo_mas_usado,
        'pastel_clientes': pastel_clientes,
        'admin_usuario': usuario,
    }
    return render(request, 'admin/admin_dashboard.html', contexto)


def admin_perfil(request):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    ahora = timezone.now()
    proximas_reservas = (
        Reserva.objects.filter(fecha_hora_inicio__gte=ahora)
        .select_related('usuario', 'vehiculo', 'servicio')
        .order_by('fecha_hora_inicio')[:5]
    )

    conteo_por_estado = Reserva.objects.values('estado_reserva').annotate(total=Count('estado_reserva'))
    estado_stats = {estado: 0 for estado, _ in Reserva.ESTADO_CHOICES}
    total_reservas = 0
    for fila in conteo_por_estado:
        estado = fila['estado_reserva']
        total = fila['total']
        estado_stats[estado] = total
        total_reservas += total

    clientes_totales = Cliente.objects.count()
    clientes_activos_30 = (
        Cliente.objects.filter(reserva__fecha_hora_inicio__gte=ahora - timedelta(days=30))
        .distinct()
        .count()
    )

    total_insumos = Insumo.objects.count()
    stock_total = Insumo.objects.aggregate(total=Sum('cantidad')).get('total') or 0
    umbral_bajo = 5
    insumos_bajos = Insumo.objects.filter(cantidad__lte=umbral_bajo).order_by('cantidad', 'nombre')

    contexto = {
        'admin_usuario': usuario,
        'total_reservas': total_reservas,
        'estado_stats': estado_stats,
        'proximas_reservas': proximas_reservas,
        'clientes_totales': clientes_totales,
        'clientes_activos_30': clientes_activos_30,
        'total_insumos': total_insumos,
        'stock_total': stock_total,
        'insumos_bajos': insumos_bajos,
        'umbral_bajo': umbral_bajo,
    }
    return render(request, 'admin/admin_perfil.html', contexto)


def admin_usuarios(request):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    clientes = Cliente.objects.all().order_by('apellido_cliente', 'nombre_cliente')

    if request.method == 'POST':
        target_id = request.POST.get('cliente_id')
        accion = request.POST.get('accion')
        if target_id and accion:
            cliente_obj = get_object_or_404(Cliente, pk=target_id)
            if accion == 'make_admin':
                if cliente_obj.es_admin:
                    messages.info(request, f'{cliente_obj.nombre_cliente} ya es administrador.')
                else:
                    cliente_obj.es_admin = True
                    cliente_obj.save()
                    messages.success(request, f'{cliente_obj.nombre_cliente} ahora es administrador.')
            elif accion == 'remove_admin':
                if cliente_obj.pk == usuario.pk:
                    messages.warning(request, 'No puedes quitar tu propio rol de administrador desde aquí.')
                elif not Cliente.objects.filter(es_admin=True).exclude(pk=cliente_obj.pk).exists():
                    messages.error(request, 'Debe existir al menos un administrador activo.')
                else:
                    cliente_obj.es_admin = False
                    cliente_obj.save()
                    messages.success(request, f'{cliente_obj.nombre_cliente} ya no es administrador.')
        return redirect('admin_usuarios')

    return render(
        request,
        'admin/admin_usuarios.html',
        {
            'clientes': clientes,
            'admin_usuario': usuario,
        },
    )


def admin_editar_reserva(request, id):
    usuario, respuesta = _require_admin(request)
    if respuesta:
        return respuesta

    reserva = get_object_or_404(Reserva, pk=id)

    class AdminReservaForm(forms.ModelForm):
        class Meta:
            model = Reserva
            fields = ['estado_reserva', 'notas_cliente', 'direccion_reserva', 'comuna_reserva']

    if request.method == 'POST':
        form = AdminReservaForm(request.POST, instance=reserva)
        if form.is_valid():
            form.save()
            messages.success(request, 'Reserva actualizada correctamente.')
            return redirect('admin_dashboard')
    else:
        form = AdminReservaForm(instance=reserva)

    return render(
        request,
        'admin/admin_editar_reserva.html',
        {
            'form': form,
            'reserva': reserva,
            'admin_usuario': usuario,
        },
    )


# -----------------------
# Vistas para clientes
# -----------------------

def editar_reserva(request, id):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    reserva = get_object_or_404(Reserva, pk=id, usuario_id=cliente_id)
    if reserva.estado_reserva != 'Pendiente':
        messages.error(request, 'Solo puedes editar reservas pendientes.')
        return redirect('ver_perfil')

    vehiculos = Vehiculo.objects.filter(usuario_id=cliente_id)
    servicios = Servicio.objects.all()
    reservas_existentes = Reserva.objects.exclude(pk=reserva.pk)

    if request.method == 'POST':
        form = ReservaForm(request.POST, instance=reserva)
        form.fields['vehiculo'].queryset = vehiculos
        form.fields['servicio'].queryset = servicios
        if form.is_valid():
            nueva_reserva = form.save(commit=False)
            hora_inicio = nueva_reserva.fecha_hora_inicio.time()
            if not (time(10, 0) <= hora_inicio <= time(18, 30)):
                messages.error(request, 'El horario de reservas es entre 10:00 y 18:30.')
            else:
                nueva_inicio = nueva_reserva.fecha_hora_inicio
                nueva_fin = nueva_inicio + timedelta(hours=2, minutes=30)
                solapada = False
                for r in reservas_existentes:
                    inicio = r.fecha_hora_inicio
                    fin = inicio + timedelta(hours=2, minutes=30)
                    if nueva_inicio < fin and nueva_fin > inicio:
                        solapada = True
                        break
                if solapada:
                    messages.error(request, 'Ya existe una reserva en ese horario o se solapa con otra. Elige otro horario.')
                else:
                    nueva_reserva.save()
                    cliente = Cliente.objects.get(pk=cliente_id)
                    send_mail(
                        'Actualización de Reserva - Vasquez Garaje',
                        (
                            f"Estimado/a {cliente.nombre_cliente},\n\n"
                            "Su reserva ha sido actualizada para el día "
                            f"{nueva_reserva.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')} "
                            f"para el vehículo con patente {nueva_reserva.patente}.\n\n"
                            "Gracias por preferirnos."
                        ),
                        'no-reply@vasquezgaraje.cl',
                        [cliente.correo_cliente],
                        fail_silently=True,
                    )
                    messages.success(request, 'Reserva actualizada correctamente. Se ha enviado un correo de confirmación.')
                    return redirect('ver_perfil')
    else:
        form = ReservaForm(instance=reserva)
        form.fields['vehiculo'].queryset = vehiculos
        form.fields['servicio'].queryset = servicios

    hoy = datetime.now().strftime('%Y-%m-%d')
    min_datetime = f"{hoy}T10:00"
    max_datetime = f"{hoy}T18:30"

    return render(
        request,
        'editar_reserva.html',
        {
            'form': form,
            'reserva': reserva,
            'min_datetime': min_datetime,
            'max_datetime': max_datetime,
        },
    )


def cancelar_reserva(request, id):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    reserva = get_object_or_404(Reserva, pk=id, usuario_id=cliente_id)
    if reserva.estado_reserva not in ['Pendiente', 'Confirmado']:
        messages.error(request, 'Solo puedes cancelar reservas pendientes o confirmadas.')
        return redirect('ver_perfil')

    reserva.estado_reserva = 'Cancelado'
    reserva.save()
    messages.success(request, 'Reserva cancelada correctamente.')
    return redirect('ver_perfil')


class EditarPerfilForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre_cliente', 'apellido_cliente', 'correo_cliente', 'telefono_cliente']


def editar_perfil(request):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    usuario = get_object_or_404(Cliente, pk=cliente_id)

    if request.method == 'POST':
        form = EditarPerfilForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            _set_cliente_session(request, usuario)
            messages.success(request, 'Perfil actualizado correctamente.')
            return redirect('ver_perfil')
    else:
        form = EditarPerfilForm(instance=usuario)

    return render(request, 'editar_perfil.html', {'form': form, 'usuario': usuario})


# -----------------------
# Autenticación y páginas generales
# -----------------------

def home(request):
    return render(request, 'home.html')


def login(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            correo = form.cleaned_data['correo_cliente']
            contraseña = form.cleaned_data['contraseña_cliente']
            try:
                cliente = Cliente.objects.get(correo_cliente=correo)
                if check_password(contraseña, cliente.contraseña_cliente):
                    _set_cliente_session(request, cliente)
                    messages.success(request, 'Inicio de sesión exitoso.')
                    if cliente.es_admin:
                        return redirect('admin_perfil')
                    return redirect('ver_perfil')
                else:
                    messages.error(request, 'Contraseña incorrecta.')
            except Cliente.DoesNotExist:
                messages.error(request, 'Correo no registrado.')
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


def logout(request):
    django_logout(request)
    _clear_cliente_session(request)
    storage = messages.get_messages(request)
    for _ in storage:
        pass
    messages.success(request, 'Sesión cerrada correctamente.')
    return redirect('login')


def registro(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            raw_password = form.cleaned_data.get('contraseña_cliente')
            cliente.contraseña_cliente = make_password(raw_password)
            cliente.save()
            messages.success(request, 'Registro exitoso. Ahora puedes iniciar sesión.')
            return redirect('login')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = RegistroForm()
    return render(request, 'registro.html', {'form': form})


def recuperar_contraseña(request):
    return render(request, 'recuperar_contraseña.html')


def inventario(request):
    return render(request, 'inventario.html')


def admin_control(request):
    return render(request, 'admin_control.html')


def agendar_servicio(request):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    vehiculos = Vehiculo.objects.filter(usuario_id=cliente_id)
    servicios = Servicio.objects.all()
    reservas_existentes = Reserva.objects.all()

    if request.method == 'POST':
        form = ReservaForm(request.POST)
        form.fields['vehiculo'].queryset = vehiculos
        form.fields['servicio'].queryset = servicios
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.usuario_id = cliente_id
            reserva.estado_reserva = 'Pendiente'
            hora_inicio = reserva.fecha_hora_inicio.time()
            if not (time(10, 0) <= hora_inicio <= time(18, 30)):
                messages.error(request, 'El horario de reservas es entre 10:00 y 18:30.')
            else:
                nueva_inicio = reserva.fecha_hora_inicio
                nueva_fin = nueva_inicio + timedelta(hours=2, minutes=30)
                solapada = False
                for r in reservas_existentes:
                    inicio = r.fecha_hora_inicio
                    fin = inicio + timedelta(hours=2, minutes=30)
                    if nueva_inicio < fin and nueva_fin > inicio:
                        solapada = True
                        break
                if solapada:
                    messages.error(request, 'Ya existe una reserva en ese horario o se solapa con otra. Elige otro horario.')
                else:
                    reserva.save()
                    cliente = Cliente.objects.get(pk=cliente_id)
                    send_mail(
                        'Confirmación de Reserva - Vasquez Garaje',
                        (
                            f"Estimado/a {cliente.nombre_cliente},\n\n"
                            "Su reserva ha sido registrada para el día "
                            f"{reserva.fecha_hora_inicio.strftime('%d/%m/%Y a las %H:%M')} "
                            f"para el vehículo con patente {reserva.patente}.\n\n"
                            "Gracias por preferirnos."
                        ),
                        'no-reply@vasquezgaraje.cl',
                        [cliente.correo_cliente],
                        fail_silently=True,
                    )
                    messages.success(request, 'Reserva realizada exitosamente. Se ha enviado un correo de confirmación.')
                    return redirect('perfil_usuario')
    else:
        form = ReservaForm()
        form.fields['vehiculo'].queryset = vehiculos
        form.fields['servicio'].queryset = servicios

    horarios_ocupados = [
        {
            'inicio': r.fecha_hora_inicio.strftime('%Y-%m-%dT%H:%M'),
            'fin': (r.fecha_hora_inicio + timedelta(hours=2, minutes=30)).strftime('%Y-%m-%dT%H:%M'),
        }
        for r in reservas_existentes
    ]

    hoy = datetime.now().strftime('%Y-%m-%d')
    min_datetime = f"{hoy}T10:00"
    max_datetime = f"{hoy}T18:30"

    return render(
        request,
        'agendar_servicio.html',
        {
            'form': form,
            'horarios_ocupados': horarios_ocupados,
            'vehiculos': vehiculos,
            'servicios': servicios,
            'min_datetime': min_datetime,
            'max_datetime': max_datetime,
        },
    )


def perfil_usuario(request):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    vehiculos = Vehiculo.objects.filter(usuario_id=cliente_id)
    reservas = Reserva.objects.filter(vehiculo__in=vehiculos).select_related('servicio', 'vehiculo')

    return render(
        request,
        'perfil_usuario.html',
        {
            'reservas': reservas,
            'vehiculos': vehiculos,
        },
    )
