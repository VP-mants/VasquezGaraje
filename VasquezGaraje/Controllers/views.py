from django.shortcuts import render, redirect
from Models.models import Cliente
from Controllers.forms import RegistroForm, LoginForm
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
	return render(request, 'agendar_servicio.html')
