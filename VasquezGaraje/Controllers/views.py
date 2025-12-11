import json
from datetime import datetime, timedelta, time
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth import logout as django_logout
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count, Max, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from Controllers.forms import CambiarContrasenaForm, LoginForm, RegistroForm
from Controllers.reserva_forms import (
    ReservaForm,
    ensure_servicios_predeterminados,
    get_servicios_ordenados,
)
from Models.models import Cliente, Insumo, Reserva, ReservaInsumo, Servicio, Vehiculo


RESERVA_DURACION = timedelta(hours=1, minutes=30)
HORARIO_APERTURA = time(10, 0)
HORARIO_CIERRE = time(18, 30)


def _calcular_min_datetime_reserva():
    """Devuelve la primera fecha disponible respetando la jornada y el momento actual."""
    ahora = timezone.localtime()

    if ahora.time() < HORARIO_APERTURA:
        return _asegurar_aware(datetime.combine(ahora.date(), HORARIO_APERTURA))

    if ahora.time() > HORARIO_CIERRE:
        siguiente = ahora.date() + timedelta(days=1)
        return _asegurar_aware(datetime.combine(siguiente, HORARIO_APERTURA))

    candidato = ahora.replace(second=0, microsecond=0)
    resto = candidato.minute % 30
    if resto != 0:
        candidato += timedelta(minutes=30 - resto)

    if candidato.time() > HORARIO_CIERRE:
        siguiente = ahora.date() + timedelta(days=1)
        return _asegurar_aware(datetime.combine(siguiente, HORARIO_APERTURA))

    return candidato


def _formatear_datetime_para_input(valor):
    """Formatea una fecha con zona horaria a la cadena esperada por inputs HTML."""
    localizado = timezone.localtime(valor)
    return localizado.strftime('%Y-%m-%dT%H:%M')


def _configurar_widget_fecha(formulario, min_datetime_str):
    min_date = min_datetime_str.split('T')[0]

    if 'fecha_hora_inicio' in formulario.fields:
        formulario.fields['fecha_hora_inicio'].widget = forms.HiddenInput()
        formulario.fields['fecha_hora_inicio'].required = False

    fecha_field = formulario.fields.get('fecha_reserva')
    if fecha_field:
        fecha_field.widget.attrs.setdefault('class', 'input-box')
        fecha_field.widget.attrs['min'] = min_date

    hora_field = formulario.fields.get('hora_reserva')
    if hora_field:
        hora_field.widget.attrs.setdefault('class', 'input-box')


def _asegurar_aware(fecha):
    if timezone.is_naive(fecha):
        return timezone.make_aware(fecha, timezone.get_current_timezone())
    return fecha


def _es_intervalo_media_hora(fecha):
    return fecha.minute in (0, 30) and fecha.second == 0 and fecha.microsecond == 0


def _obtener_o_crear_vehiculo(usuario, descripcion, patente):
    if not patente:
        raise ValueError('Debes ingresar la patente del vehículo.')

    patente_normalizada = patente.strip().upper()
    descripcion = (descripcion or '').strip()

    vehiculo, creado = Vehiculo.objects.get_or_create(
        patente=patente_normalizada,
        defaults={'usuario': usuario},
    )

    necesita_guardar = creado

    if vehiculo.usuario_id != usuario.pk:
        vehiculo.usuario = usuario
        necesita_guardar = True

    if descripcion:
        descripcion_corta = descripcion[:50]
        if vehiculo.marca != descripcion_corta:
            vehiculo.marca = descripcion_corta
            necesita_guardar = True

    if necesita_guardar:
        vehiculo.save()

    return vehiculo


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

    ensure_insumos_predeterminados()

    return usuario, None


def _set_cliente_session(request, cliente):
    request.session['cliente_id'] = cliente.cliente_id
    request.session['nombre_cliente'] = cliente.nombre_cliente
    request.session['apellido_cliente'] = cliente.apellido_cliente
    request.session['es_admin'] = cliente.es_admin


def _clear_cliente_session(request):
    for key in ['cliente_id', 'nombre_cliente', 'apellido_cliente', 'es_admin']:
        request.session.pop(key, None)


_INSUMOS_PREDETERMINADOS = (
    {
        'nombre': 'Aceite 10W-40',
        'descripcion': 'Lubricante multigrado para motores a gasolina.',
        'cantidad': 12,
        'unidad_medida': 'litros',
        'precio_unitario': Decimal('15990.00'),
    },
    {
        'nombre': 'Filtro de aceite',
        'descripcion': 'Repuesto compatible con modelos sedán y hatchback.',
        'cantidad': 20,
        'unidad_medida': 'unidad',
        'precio_unitario': Decimal('8990.00'),
    },
    {
        'nombre': 'Líquido de frenos DOT4',
        'descripcion': 'Fluido para mantenimientos correctivos del sistema de frenos.',
        'cantidad': 10,
        'unidad_medida': 'litros',
        'precio_unitario': Decimal('12990.00'),
    },
)


def ensure_insumos_predeterminados():
    if Insumo.objects.exists():
        return

    for datos in _INSUMOS_PREDETERMINADOS:
        Insumo.objects.get_or_create(
            nombre=datos['nombre'],
            defaults={
                'descripcion': datos['descripcion'],
                'cantidad': datos['cantidad'],
                'unidad_medida': datos['unidad_medida'],
                'precio_unitario': datos['precio_unitario'],
            },
        )


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
    reservas_qs = (
        Reserva.objects.all()
        .select_related('usuario', 'vehiculo', 'servicio')
        .order_by('-fecha_hora_inicio')
    )
    if filtro_estado:
        reservas_qs = reservas_qs.filter(estado_reserva=filtro_estado)

    reservas_detalle = []
    for reserva in reservas_qs:
        inicio_local = timezone.localtime(_asegurar_aware(reserva.fecha_hora_inicio))
        fin_local = inicio_local + RESERVA_DURACION
        reservas_detalle.append(
            {
                'id': reserva.reserva_id,
                'cliente_nombre': f"{reserva.usuario.nombre_cliente} {reserva.usuario.apellido_cliente}".strip(),
                'vehiculo': getattr(reserva.vehiculo, 'patente', str(reserva.vehiculo)),
                'servicio': getattr(reserva.servicio, 'nombre_servicio', str(reserva.servicio)),
                'inicio': inicio_local,
                'fin': fin_local,
                'estado': reserva.estado_reserva,
            }
        )

    hoy = timezone.now()
    reservas_mes = Reserva.objects.filter(
        fecha_hora_inicio__year=hoy.year,
        fecha_hora_inicio__month=hoy.month,
    )
    total_reservas_mes = reservas_mes.count()
    ingresos_estimados_mes = sum([r.servicio.duracion_servicio * 10 for r in reservas_mes])

    clientes_resumen_qs = (
        Reserva.objects.all()
        .values('usuario_id', 'usuario__nombre_cliente', 'usuario__apellido_cliente')
        .annotate(total=Count('reserva_id'), ultima=Max('fecha_hora_inicio'))
        .order_by('-total', 'usuario__nombre_cliente', 'usuario__apellido_cliente')
    )

    clientes_resumen = []
    for fila in clientes_resumen_qs[:8]:
        ultima_inicio = fila['ultima']
        ultima_inicio_local = None
        ultima_fin_local = None
        if ultima_inicio:
            ultima_inicio_local = timezone.localtime(_asegurar_aware(ultima_inicio))
            ultima_fin_local = ultima_inicio_local + RESERVA_DURACION
        clientes_resumen.append(
            {
                'nombre': f"{fila['usuario__nombre_cliente']} {fila['usuario__apellido_cliente']}".strip(),
                'total': fila['total'],
                'ultima_inicio': ultima_inicio_local,
                'ultima_fin': ultima_fin_local,
            }
        )

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
        'reservas_detalle': reservas_detalle,
        'reservas_total': len(reservas_detalle),
        'clientes_resumen': clientes_resumen,
        'filtro_estado': filtro_estado,
        'estado_opciones': Reserva.ESTADO_CHOICES,
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

    estado_chart_labels = []
    estado_chart_data = []
    for estado_codigo, estado_etiqueta in Reserva.ESTADO_CHOICES:
        estado_chart_labels.append(estado_etiqueta)
        estado_chart_data.append(estado_stats.get(estado_codigo, 0))

    clientes_totales = Cliente.objects.count()
    clientes_activos_30 = (
        Cliente.objects.filter(reserva__fecha_hora_inicio__gte=ahora - timedelta(days=30))
        .distinct()
        .count()
    )
    clientes_inactivos_30 = max(clientes_totales - clientes_activos_30, 0)

    clientes_chart_labels = [
        'Activos últimos 30 días',
        'Inactivos últimos 30 días',
    ]
    clientes_chart_data = [clientes_activos_30, clientes_inactivos_30]

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
        'estado_chart_labels': estado_chart_labels,
        'estado_chart_data': estado_chart_data,
        'clientes_chart_labels': clientes_chart_labels,
        'clientes_chart_data': clientes_chart_data,
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

    class ReservaInsumoForm(forms.Form):
        insumo = forms.ModelChoiceField(
            queryset=Insumo.objects.none(),
            required=False,
            label='Insumo',
            widget=forms.Select(attrs={'class': 'admin-insumo-select'}),
        )
        cantidad = forms.IntegerField(
            required=False,
            label='Cantidad utilizada',
            min_value=0,
            widget=forms.NumberInput(attrs={'class': 'admin-insumo-qty', 'min': 0, 'step': 1}),
        )

        def __init__(self, *args, **kwargs):
            insumo_queryset = kwargs.pop('insumo_queryset', Insumo.objects.none())
            super().__init__(*args, **kwargs)
            self.fields['insumo'].queryset = insumo_queryset
            self.fields['insumo'].label_from_instance = (
                lambda obj: f"{obj.nombre} (stock: {obj.cantidad} {obj.unidad_medida})"
            )

        def clean(self):
            cleaned_data = super().clean()
            if cleaned_data.get('DELETE'):
                return cleaned_data

            insumo = cleaned_data.get('insumo')
            cantidad = cleaned_data.get('cantidad')

            if insumo and (cantidad is None or cantidad <= 0):
                self.add_error('cantidad', 'Ingresa una cantidad mayor a cero.')

            if cantidad and not insumo:
                self.add_error('insumo', 'Selecciona un insumo.')

            if not insumo:
                cleaned_data['cantidad'] = 0

            return cleaned_data

    ReservaInsumoFormSet = forms.formset_factory(ReservaInsumoForm, extra=1, can_delete=True)

    relaciones_existentes = list(reserva.insumos_utilizados.select_related('insumo'))
    insumos_queryset = Insumo.objects.order_by('nombre')
    inicial_insumos = [
        {'insumo': relacion.insumo_id, 'cantidad': relacion.cantidad_utilizada}
        for relacion in relaciones_existentes
    ]

    if request.method == 'POST':
        form = AdminReservaForm(request.POST, instance=reserva)
        formset = ReservaInsumoFormSet(
            request.POST,
            prefix='insumos',
            form_kwargs={'insumo_queryset': insumos_queryset},
        )
        form_es_valido = form.is_valid()
        formset_es_valido = formset.is_valid()
        if form_es_valido and formset_es_valido:
                existentes_cantidades = {
                    relacion.insumo_id: relacion.cantidad_utilizada for relacion in relaciones_existentes
                }
                existentes_objetos = {relacion.insumo_id: relacion for relacion in relaciones_existentes}

                nuevos_totales = {}
                formularios_por_insumo = {}
                for indice, formulario in enumerate(formset.forms):
                    datos = formulario.cleaned_data
                    if not datos or datos.get('DELETE'):
                        continue

                    insumo = datos.get('insumo')
                    cantidad = datos.get('cantidad') or 0

                    if not insumo or cantidad <= 0:
                        continue

                    insumo_id = insumo.pk
                    nuevos_totales[insumo_id] = nuevos_totales.get(insumo_id, 0) + cantidad
                    formularios_por_insumo.setdefault(insumo_id, []).append(formulario)

                ids_todos = set(existentes_cantidades.keys()) | set(nuevos_totales.keys())
                insumos_objetos = {
                    obj.pk: obj for obj in Insumo.objects.filter(pk__in=ids_todos)
                }

                error_stock = False
                for insumo_id in ids_todos:
                    insumo_obj = insumos_objetos.get(insumo_id)
                    if not insumo_obj:
                        continue
                    cantidad_antigua = existentes_cantidades.get(insumo_id, 0)
                    cantidad_nueva = nuevos_totales.get(insumo_id, 0)
                    delta = cantidad_nueva - cantidad_antigua

                    if delta > 0 and insumo_obj.cantidad < delta:
                        error_stock = True
                        for formulario in formularios_por_insumo.get(insumo_id, []):
                            formulario.add_error(
                                'cantidad',
                                f"Solo hay {insumo_obj.cantidad} {insumo_obj.unidad_medida} disponibles en inventario.",
                            )

                if not error_stock:
                    with transaction.atomic():
                        form.save()

                        insumos_bloqueados = {
                            obj.pk: obj
                            for obj in Insumo.objects.select_for_update().filter(pk__in=ids_todos)
                        }

                        for insumo_id in ids_todos:
                            insumo_obj = insumos_bloqueados.get(insumo_id)
                            if not insumo_obj:
                                continue
                            cantidad_antigua = existentes_cantidades.get(insumo_id, 0)
                            cantidad_nueva = nuevos_totales.get(insumo_id, 0)
                            delta = cantidad_nueva - cantidad_antigua

                            if delta != 0:
                                insumo_obj.cantidad -= delta
                                insumo_obj.save(update_fields=['cantidad', 'fecha_actualizacion'])

                        for insumo_id, cantidad in nuevos_totales.items():
                            relacion = existentes_objetos.get(insumo_id)
                            if relacion:
                                if relacion.cantidad_utilizada != cantidad:
                                    relacion.cantidad_utilizada = cantidad
                                    relacion.save(update_fields=['cantidad_utilizada'])
                            else:
                                ReservaInsumo.objects.create(
                                    reserva=reserva,
                                    insumo_id=insumo_id,
                                    cantidad_utilizada=cantidad,
                                )

                        for insumo_id in list(existentes_cantidades.keys()):
                            if insumo_id not in nuevos_totales:
                                existentes_objetos[insumo_id].delete()

                    messages.success(request, 'Reserva actualizada correctamente.')
                    return redirect('admin_dashboard')
    else:
        form = AdminReservaForm(instance=reserva)
        formset = ReservaInsumoFormSet(
            initial=inicial_insumos,
            prefix='insumos',
            form_kwargs={'insumo_queryset': insumos_queryset},
        )

    return render(
        request,
        'admin/admin_editar_reserva.html',
        {
            'form': form,
            'reserva': reserva,
            'admin_usuario': usuario,
            'insumos_formset': formset,
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

    servicios = get_servicios_ordenados()
    reservas_existentes = Reserva.objects.exclude(pk=reserva.pk).exclude(estado_reserva='Cancelado')

    min_datetime_obj = _calcular_min_datetime_reserva()
    min_datetime_str = _formatear_datetime_para_input(min_datetime_obj)

    if request.method == 'POST':
        form = ReservaForm(request.POST, instance=reserva)
    else:
        form = ReservaForm(instance=reserva)

    form.fields['servicio'].queryset = servicios
    form.fields['servicio'].empty_label = 'Selecciona un servicio'
    _configurar_widget_fecha(form, min_datetime_str)

    def _add_slot_error(message, include_date=False):
        if include_date:
            form.add_error('fecha_reserva', message)
        form.add_error('hora_reserva', message)
        form.add_error('fecha_hora_inicio', message)

    if request.method == 'POST' and form.is_valid():
        descripcion = form.cleaned_data.get('vehiculo_texto')
        patente = form.cleaned_data.get('patente')

        try:
            vehiculo = _obtener_o_crear_vehiculo(reserva.usuario, descripcion, patente)
        except ValueError as error:
            form.add_error('patente', error)
        else:
            nueva_reserva = form.save(commit=False)
            nueva_reserva.vehiculo = vehiculo
            nueva_reserva.patente = vehiculo.patente
            nueva_inicio = _asegurar_aware(nueva_reserva.fecha_hora_inicio)
            inicio_local = timezone.localtime(nueva_inicio)

            if inicio_local < min_datetime_obj:
                _add_slot_error('No puedes seleccionar un horario en el pasado.', include_date=True)
            elif not _es_intervalo_media_hora(inicio_local):
                _add_slot_error('Selecciona horarios en bloques de 30 minutos.')
            else:
                hora_inicio = inicio_local.time()
                if not (HORARIO_APERTURA <= hora_inicio <= HORARIO_CIERRE):
                    _add_slot_error('El horario de reservas es entre 10:00 y 18:30.')
                else:
                    nueva_fin = nueva_inicio + RESERVA_DURACION
                    solapada = False
                    for r in reservas_existentes:
                        inicio_existente = _asegurar_aware(r.fecha_hora_inicio)
                        fin_existente = inicio_existente + RESERVA_DURACION
                        if nueva_inicio < fin_existente and nueva_fin > inicio_existente:
                            solapada = True
                            break
                    if solapada:
                        _add_slot_error('Ya existe una reserva en ese horario o se solapa con otra. Elige otro horario.')
                    else:
                        nueva_reserva.save()
                        cliente = reserva.usuario
                        send_mail(
                            'Actualización de Reserva - VasquezGarage SPA',
                            (
                                f"Estimado/a {cliente.nombre_cliente},\n\n"
                                "Su reserva ha sido actualizada para el día "
                                f"{inicio_local.strftime('%d/%m/%Y a las %H:%M')} "
                                f"para el vehículo con patente {nueva_reserva.patente}.\n\n"
                                "Gracias por preferirnos."
                            ),
                            'no-reply@vasquezgaraje.cl',
                            [cliente.correo_cliente],
                            fail_silently=True,
                        )
                        messages.success(request, 'Reserva actualizada correctamente. Se ha enviado un correo de confirmación.')
                        return redirect('ver_perfil')

    return render(
        request,
        'editar_reserva.html',
        {
            'form': form,
            'reserva': reserva,
        },
    )


def cancelar_reserva(request, id):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    if request.method != 'POST':
        messages.error(request, 'Acción inválida para cancelar la reserva.')
        return redirect('ver_perfil')

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


def cambiar_contrasena(request):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    usuario = get_object_or_404(Cliente, pk=cliente_id)

    if request.method == 'POST':
        form = CambiarContrasenaForm(request.POST)
        if form.is_valid():
            actual = form.cleaned_data['contrasena_actual']
            if not check_password(actual, usuario.contraseña_cliente):
                form.add_error('contrasena_actual', 'La contraseña actual no es correcta.')
            else:
                nueva = form.cleaned_data['nueva_contrasena']
                usuario.contraseña_cliente = make_password(nueva)
                usuario.save()
                messages.success(request, 'Contraseña actualizada correctamente.')
                return redirect('ver_perfil')
    else:
        form = CambiarContrasenaForm()

    return render(request, 'cambiar_contrasena.html', {'form': form, 'usuario': usuario})


# -----------------------
# Autenticación y páginas generales
# -----------------------

def home(request):
    ensure_servicios_predeterminados()

    nombres_servicios = ['Consulta', 'Mantenimiento', 'Otros']
    servicios_qs = Servicio.objects.filter(nombre_servicio__in=nombres_servicios)
    servicios_map = {serv.nombre_servicio.lower(): serv for serv in servicios_qs}

    descripciones_default = {
        'consulta': 'Asesoría experta para diagnosticar y planificar el servicio que necesita tu vehículo.',
        'mantenimiento': 'Programas de mantenimiento preventivo para mantener tu auto en óptimas condiciones.',
        'otros': 'Servicios personalizados, cuéntanos tu necesidad y coordinamos la solución ideal.',
    }

    servicios_destacados = []
    for nombre in nombres_servicios:
        clave = nombre.lower()
        servicio = servicios_map.get(clave)
        descripcion = (servicio.descripcion_servicio.strip() if servicio and servicio.descripcion_servicio else '')
        if not descripcion:
            descripcion = descripciones_default.get(clave, '')
        servicios_destacados.append({'titulo': nombre, 'descripcion': descripcion})

    contexto = {'servicios_destacados': servicios_destacados}
    return render(request, 'home.html', contexto)


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
    servicios = get_servicios_ordenados()
    reservas_existentes = (
        Reserva.objects.exclude(estado_reserva='Cancelado')
        .select_related('vehiculo', 'servicio', 'usuario')
    )

    min_datetime_obj = _calcular_min_datetime_reserva()
    min_datetime_str = _formatear_datetime_para_input(min_datetime_obj)

    min_local = timezone.localtime(min_datetime_obj)

    if request.method == 'POST':
        form = ReservaForm(request.POST)
    else:
        form = ReservaForm(
            initial={
                'fecha_reserva': min_local.date(),
                'hora_reserva': min_local.strftime('%H:%M'),
            }
        )

    form.fields['servicio'].queryset = servicios
    form.fields['servicio'].empty_label = 'Selecciona un servicio'
    _configurar_widget_fecha(form, min_datetime_str)

    def _add_slot_error(message, include_date=False):
        if include_date:
            form.add_error('fecha_reserva', message)
        form.add_error('hora_reserva', message)
        form.add_error('fecha_hora_inicio', message)

    if request.method == 'POST' and form.is_valid():
        cliente = Cliente.objects.get(pk=cliente_id)
        descripcion = form.cleaned_data.get('vehiculo_texto')
        patente = form.cleaned_data.get('patente')

        try:
            vehiculo = _obtener_o_crear_vehiculo(cliente, descripcion, patente)
        except ValueError as error:
            form.add_error('patente', error)
        else:
            reserva = form.save(commit=False)
            reserva.usuario = cliente
            reserva.vehiculo = vehiculo
            reserva.patente = vehiculo.patente
            reserva.estado_reserva = 'Pendiente'

            inicio_aware = _asegurar_aware(reserva.fecha_hora_inicio)
            inicio_local = timezone.localtime(inicio_aware)

            if inicio_local < min_datetime_obj:
                _add_slot_error('No puedes agendar en un horario anterior al disponible.', include_date=True)
            elif not _es_intervalo_media_hora(inicio_local):
                _add_slot_error('Selecciona horarios en bloques de 30 minutos.')
            else:
                hora_inicio = inicio_local.time()
                if not (HORARIO_APERTURA <= hora_inicio <= HORARIO_CIERRE):
                    _add_slot_error('El horario de reservas es entre 10:00 y 18:30.')
                else:
                    nueva_fin = inicio_aware + RESERVA_DURACION
                    solapada = False
                    for r in reservas_existentes:
                        inicio_existente = _asegurar_aware(r.fecha_hora_inicio)
                        fin_existente = inicio_existente + RESERVA_DURACION
                        if inicio_aware < fin_existente and nueva_fin > inicio_existente:
                            solapada = True
                            break

                    if solapada:
                        _add_slot_error('Ya existe una reserva en ese horario o se solapa con otra. Elige otro horario.')
                    else:
                        reserva.fecha_hora_inicio = inicio_aware
                        reserva.save()
                        send_mail(
                            'Confirmación de Reserva - VasquezGarage SPA',
                            (
                                f"Estimado/a {cliente.nombre_cliente},\n\n"
                                "Su reserva ha sido registrada para el día "
                                f"{inicio_local.strftime('%d/%m/%Y a las %H:%M')} "
                                f"para el vehículo con patente {reserva.patente}.\n\n"
                                "Gracias por preferirnos."
                            ),
                            'no-reply@vasquezgaraje.cl',
                            [cliente.correo_cliente],
                            fail_silently=True,
                        )
                        messages.success(request, 'Reserva realizada exitosamente. Se ha enviado un correo de confirmación.')
                        return redirect('ver_perfil')

    reservas_agendadas = []
    reservas_eventos = []
    reservas_futuras = reservas_existentes.filter(fecha_hora_inicio__gte=timezone.now()).order_by(
        'fecha_hora_inicio'
    )

    for r in reservas_futuras:
        inicio_local = timezone.localtime(_asegurar_aware(r.fecha_hora_inicio))
        fin_local = inicio_local + RESERVA_DURACION
        servicio_nombre = getattr(r.servicio, 'nombre_servicio', str(r.servicio))
        vehiculo_patente = getattr(r.vehiculo, 'patente', str(r.vehiculo))
        es_propia = r.usuario_id == cliente_id
        reservas_agendadas.append(
            {
                'fecha': inicio_local,
                'fecha_label': date_format(inicio_local, "l d \d\e F"),
                'hora_inicio': inicio_local.strftime('%H:%M'),
                'hora_fin': fin_local.strftime('%H:%M'),
                'servicio': servicio_nombre,
                'vehiculo': vehiculo_patente,
                'estado': r.estado_reserva,
                'es_propia': es_propia,
            }
        )
        reservas_eventos.append(
            {
                'title': 'Reservado',
                'start': inicio_local.isoformat(),
                'end': fin_local.isoformat(),
                'extendedProps': {
                    'estado': r.estado_reserva,
                    'servicio': servicio_nombre,
                    'vehiculo': vehiculo_patente,
                    'esPropia': es_propia,
                },
            }
        )

    return render(
        request,
        'agendar_servicio.html',
        {
            'form': form,
            'servicios': servicios,
            'reservas_agendadas': reservas_agendadas,
            'reservas_eventos_json': json.dumps(reservas_eventos, ensure_ascii=False),
        },
    )


def perfil_usuario(request):
    if not request.session.get('cliente_id'):
        return redirect('login')

    cliente_id = request.session['cliente_id']
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    vehiculos = Vehiculo.objects.filter(usuario_id=cliente_id)
    reservas = (
        Reserva.objects.filter(usuario_id=cliente_id)
        .select_related('servicio', 'vehiculo')
        .order_by('-fecha_hora_inicio')
    )
    reservas_totales = reservas.count()
    reservas_activas = reservas.exclude(estado_reserva='Cancelado').count()
    vehiculos_totales = vehiculos.count()
    proxima_reserva = (
        reservas.exclude(estado_reserva='Cancelado')
        .filter(fecha_hora_inicio__gte=timezone.now())
        .order_by('fecha_hora_inicio')
        .first()
    )

    return render(
        request,
        'perfil_usuario.html',
        {
            'cliente': cliente,
            'reservas': reservas,
            'vehiculos': vehiculos,
            'reservas_totales': reservas_totales,
            'reservas_activas': reservas_activas,
            'vehiculos_totales': vehiculos_totales,
            'proxima_reserva': proxima_reserva,
        },
    )
