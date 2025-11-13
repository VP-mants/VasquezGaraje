from django.urls import reverse
from django.http import HttpResponseRedirect
# CRUD Insumos para admin
def admin_insumo_nuevo(request):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	usuario = get_object_or_404(Cliente, pk=cliente_id)
	if not usuario.es_admin:
		messages.error(request, 'Acceso restringido solo para administradores.')
		return redirect('home')
	from django import forms
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
	return render(request, 'admin/admin_insumo_form.html', {'form': form, 'accion': 'Nuevo'})

def admin_insumo_editar(request, id):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	usuario = get_object_or_404(Cliente, pk=cliente_id)
	if not usuario.es_admin:
		messages.error(request, 'Acceso restringido solo para administradores.')
		return redirect('home')
	insumo = get_object_or_404(Insumo, pk=id)
	from django import forms
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
	return render(request, 'admin/admin_insumo_form.html', {'form': form, 'accion': 'Editar'})

def admin_insumo_eliminar(request, id):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	usuario = get_object_or_404(Cliente, pk=cliente_id)
	if not usuario.es_admin:
		messages.error(request, 'Acceso restringido solo para administradores.')
		return redirect('home')
	insumo = get_object_or_404(Insumo, pk=id)
	if request.method == 'POST':
		insumo.delete()
		messages.success(request, 'Insumo eliminado correctamente.')
		return redirect('admin_inventario')
	return render(request, 'admin/admin_insumo_eliminar.html', {'insumo': insumo})
from Models.models import Insumo
def admin_inventario(request):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	usuario = get_object_or_404(Cliente, pk=cliente_id)
	if not usuario.es_admin:
		messages.error(request, 'Acceso restringido solo para administradores.')
		return redirect('home')
	insumos = Insumo.objects.all().order_by('nombre')
	return render(request, 'admin/admin_inventario.html', {'insumos': insumos})
def admin_dashboard(request):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	usuario = get_object_or_404(Cliente, pk=cliente_id)
	if not usuario.es_admin:
		messages.error(request, 'Acceso restringido solo para administradores.')
		return redirect('home')
	from datetime import datetime
	filtro_estado = request.GET.get('estado', '')
	reservas = Reserva.objects.all().select_related('usuario', 'vehiculo', 'servicio')
	if filtro_estado:
		reservas = reservas.filter(estado_reserva=filtro_estado)
	# Estadísticas para análisis
	hoy = datetime.now()
	reservas_mes = Reserva.objects.filter(fecha_hora_inicio__year=hoy.year, fecha_hora_inicio__month=hoy.month)
	total_reservas_mes = reservas_mes.count()
	ingresos_estimados_mes = sum([r.servicio.duracion_servicio * 10 for r in reservas_mes])  # Ejemplo: duración*10 como valor estimado
	# Insumo más usado (simulado: el de mayor cantidad)
	try:
		from Models.models import Insumo
		insumo_mas_usado = Insumo.objects.order_by('-cantidad').first()
		insumo_mas_usado = insumo_mas_usado.nombre if insumo_mas_usado else '-'
	except:
		insumo_mas_usado = '-'

	# Clientes nuevos del mes (por patente única)
	patentes_mes = set(reservas_mes.values_list('patente', flat=True))
	patentes_anteriores = set(Reserva.objects.filter(fecha_hora_inicio__lt=reservas_mes.earliest('fecha_hora_inicio').fecha_hora_inicio if reservas_mes else hoy).values_list('patente', flat=True))
	patentes_nuevas = patentes_mes - patentes_anteriores
	total_clientes_nuevos = len(patentes_nuevas)
	total_clientes_antiguos = len(patentes_mes & patentes_anteriores)
	pastel_clientes = {
		'nuevos': total_clientes_nuevos,
		'antiguos': total_clientes_antiguos
	}

	return render(request, 'admin/admin_dashboard.html', {
		'reservas': reservas,
		'filtro_estado': filtro_estado,
		'total_reservas_mes': total_reservas_mes,
		'ingresos_estimados_mes': ingresos_estimados_mes,
		'insumo_mas_usado': insumo_mas_usado,
		'pastel_clientes': pastel_clientes,
	})

def admin_editar_reserva(request, id):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	usuario = get_object_or_404(Cliente, pk=cliente_id)
	if not usuario.es_admin:
		messages.error(request, 'Acceso restringido solo para administradores.')
		return redirect('home')
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
	return render(request, 'admin/admin_editar_reserva.html', {'form': form, 'reserva': reserva})
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
	from datetime import time, timedelta, datetime
	if request.method == 'POST':
		form = ReservaForm(request.POST, instance=reserva)
		form.fields['vehiculo'].queryset = vehiculos
		form.fields['servicio'].queryset = servicios
		if form.is_valid():
			nueva_reserva = form.save(commit=False)
			hora_inicio = nueva_reserva.fecha_hora_inicio.time()
			if not (time(10,0) <= hora_inicio <= time(18,30)):
				messages.error(request, 'El horario de reservas es entre 10:00 y 18:30.')
			else:
				nueva_inicio = nueva_reserva.fecha_hora_inicio
				nueva_fin = nueva_inicio + timedelta(hours=2, minutes=30)
				solapada = False
				for r in reservas_existentes:
					inicio = r.fecha_hora_inicio
					fin = inicio + timedelta(hours=2, minutes=30)
					if (nueva_inicio < fin and nueva_fin > inicio):
						solapada = True
						break
				if solapada:
					messages.error(request, 'Ya existe una reserva en ese horario o se solapa con otra. Elige otro horario.')
				else:
					nueva_reserva.save()
					# Enviar correo de confirmación de edición
					from django.core.mail import send_mail
					cliente = Cliente.objects.get(pk=cliente_id)
					send_mail(
						'Actualización de Reserva - Vasquez Garaje',
						f'Estimado/a {cliente.nombre_cliente},\n\nSu reserva ha sido actualizada para el día {nueva_reserva.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} para el vehículo con patente {nueva_reserva.patente}.\n\nGracias por preferirnos.',
						'no-reply@vasquezgaraje.cl',
						[cliente.correo_cliente],
						fail_silently=True
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
	return render(request, 'editar_reserva.html', {'form': form, 'reserva': reserva, 'min_datetime': min_datetime, 'max_datetime': max_datetime})

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

# Formulario para editar perfil
from django.shortcuts import render, redirect, get_object_or_404
from django import forms
from Models.models import Cliente, Reserva, Vehiculo, Servicio
from Controllers.forms import RegistroForm, LoginForm
from Controllers.reserva_forms import ReservaForm
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import logout as django_logout
from django.contrib.auth.hashers import make_password, check_password

# Formulario para editar perfil (debe ir después de importar Cliente)
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
			messages.success(request, 'Perfil actualizado correctamente.')
			return redirect('ver_perfil')
	else:
		form = EditarPerfilForm(instance=usuario)
	return render(request, 'editar_perfil.html', {'form': form, 'usuario': usuario})
from django.shortcuts import render, redirect
from Models.models import Cliente, Reserva, Vehiculo, Servicio
from Controllers.forms import RegistroForm, LoginForm
from Controllers.reserva_forms import ReservaForm
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth import logout as django_logout
from django.contrib.auth.hashers import make_password, check_password

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
					request.session['cliente_id'] = cliente.cliente_id
					request.session['nombre_cliente'] = cliente.nombre_cliente
					request.session['es_admin'] = cliente.es_admin
					messages.success(request, 'Inicio de sesión exitoso.')
					return redirect('home')
				else:
					messages.error(request, 'Contraseña incorrecta.')
			except Cliente.DoesNotExist:
				messages.error(request, 'Correo no registrado.')
	else:
		form = LoginForm()
	return render(request, 'login.html', {'form': form})

def logout(request):
	django_logout(request)
	for key in ['cliente_id', 'nombre_cliente', 'es_admin']:
		request.session.pop(key, None)
	storage = messages.get_messages(request)
	for _ in storage:
		pass  # Limpiar mensajes previos
	messages.success(request, 'Sesión cerrada correctamente.')
	from django.shortcuts import get_object_or_404
	from django import forms
	return redirect('login')

def registro(request):
	if request.method == 'POST':
		form = RegistroForm(request.POST)
		if form.is_valid():
			cliente = form.save(commit=False)
			# Hashear la contraseña antes de guardar
			raw_password = form.cleaned_data.get('contraseña_cliente')
			cliente.contraseña_cliente = make_password(raw_password)
			from django.utils.decorators import method_decorator
			from django.contrib.admin.views.decorators import staff_member_required
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
			# Validar horario permitido (10:00 a 18:30)
			hora_inicio = reserva.fecha_hora_inicio.time()
			from datetime import time, timedelta
			if not (time(10,0) <= hora_inicio <= time(18,30)):
				messages.error(request, 'El horario de reservas es entre 10:00 y 18:30.')
			else:
				# Validar solapamiento de 2h30min
				nueva_inicio = reserva.fecha_hora_inicio
				nueva_fin = nueva_inicio + timedelta(hours=2, minutes=30)
				solapada = False
				for r in reservas_existentes:
					inicio = r.fecha_hora_inicio
					fin = inicio + timedelta(hours=2, minutes=30)
					if (nueva_inicio < fin and nueva_fin > inicio):
						solapada = True
						break
				if solapada:
					messages.error(request, 'Ya existe una reserva en ese horario o se solapa con otra. Elige otro horario.')
				else:
					reserva.save()
					# Enviar correo de confirmación
					from django.core.mail import send_mail
					cliente = Cliente.objects.get(pk=cliente_id)
					send_mail(
						'Confirmación de Reserva - Vasquez Garaje',
						f'Estimado/a {cliente.nombre_cliente},\n\nSu reserva ha sido registrada para el día {reserva.fecha_hora_inicio.strftime("%d/%m/%Y a las %H:%M")} para el vehículo con patente {reserva.patente}.\n\nGracias por preferirnos.',
						'no-reply@vasquezgaraje.cl',
						[cliente.correo_cliente],
						fail_silently=True
					)
					messages.success(request, 'Reserva realizada exitosamente. Se ha enviado un correo de confirmación.')
					return redirect('perfil_usuario')
	else:
		form = ReservaForm()
		form.fields['vehiculo'].queryset = vehiculos
		form.fields['servicio'].queryset = servicios
	# Horarios ocupados como rangos para el calendario
	from datetime import timedelta
	horarios_ocupados = [
		{
			'inicio': r.fecha_hora_inicio.strftime('%Y-%m-%dT%H:%M'),
			'fin': (r.fecha_hora_inicio + timedelta(hours=2, minutes=30)).strftime('%Y-%m-%dT%H:%M')
		}
		for r in reservas_existentes
	]
	# Pasar rango de horario permitido al template para el input
	min_datetime = ''
	from datetime import datetime
	hoy = datetime.now().strftime('%Y-%m-%d')
	min_datetime = f"{hoy}T10:00"
	max_datetime = f"{hoy}T18:30"
	return render(request, 'agendar_servicio.html', {
		'form': form,
		'horarios_ocupados': horarios_ocupados,
		'vehiculos': vehiculos,
		'servicios': servicios,
		'min_datetime': min_datetime,
		'max_datetime': max_datetime
	})

def perfil_usuario(request):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	vehiculos = Vehiculo.objects.filter(usuario_id=cliente_id)
	reservas = Reserva.objects.filter(vehiculo__in=vehiculos).select_related('servicio', 'vehiculo')
	return render(request, 'perfil_usuario.html', {
		'reservas': reservas,
		'vehiculos': vehiculos
	})
