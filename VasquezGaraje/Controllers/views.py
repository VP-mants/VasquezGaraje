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
	return redirect('login')

def registro(request):
	if request.method == 'POST':
		form = RegistroForm(request.POST)
		if form.is_valid():
			cliente = form.save(commit=False)
			# Hashear la contraseña antes de guardar
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
			form.save()
			messages.success(request, 'Reserva realizada exitosamente.')
			return redirect('perfil_usuario')
	else:
		form = ReservaForm()
		form.fields['vehiculo'].queryset = vehiculos
		form.fields['servicio'].queryset = servicios
	# Horarios ocupados para mostrar en el calendario
	horarios_ocupados = [r.fecha_hora_inicio for r in reservas_existentes]
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
