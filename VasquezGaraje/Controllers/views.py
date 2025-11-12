def admin_dashboard(request):
	if not request.session.get('cliente_id'):
		return redirect('login')
	cliente_id = request.session['cliente_id']
	usuario = get_object_or_404(Cliente, pk=cliente_id)
	if not usuario.es_admin:
		messages.error(request, 'Acceso restringido solo para administradores.')
		return redirect('home')
	filtro_estado = request.GET.get('estado', '')
	reservas = Reserva.objects.all().select_related('usuario', 'vehiculo', 'servicio')
	if filtro_estado:
		reservas = reservas.filter(estado_reserva=filtro_estado)
	return render(request, 'admin/admin_dashboard.html', {
		'reservas': reservas,
		'filtro_estado': filtro_estado,
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
	if request.method == 'POST':
		form = ReservaForm(request.POST, instance=reserva)
		form.fields['vehiculo'].queryset = Vehiculo.objects.filter(usuario_id=cliente_id)
		form.fields['servicio'].queryset = Servicio.objects.all()
		if form.is_valid():
			form.save()
			messages.success(request, 'Reserva actualizada correctamente.')
			return redirect('ver_perfil')
	else:
		form = ReservaForm(instance=reserva)
		form.fields['vehiculo'].queryset = Vehiculo.objects.filter(usuario_id=cliente_id)
		form.fields['servicio'].queryset = Servicio.objects.all()
	return render(request, 'editar_reserva.html', {'form': form, 'reserva': reserva})

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
			# Validar solapamiento de 2h30min
			from datetime import timedelta
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
				messages.success(request, 'Reserva realizada exitosamente.')
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
	return render(request, 'agendar_servicio.html', {
		'form': form,
		'horarios_ocupados': horarios_ocupados,
		'vehiculos': vehiculos,
		'servicios': servicios
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
