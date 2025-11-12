from django.db import models

class Cliente(models.Model):
	cliente_id = models.AutoField(primary_key=True)
	nombre_cliente = models.CharField(max_length=100)
	apellido_cliente = models.CharField(max_length=100)
	correo_cliente = models.EmailField(unique=True)
	telefono_cliente = models.CharField(max_length=20)
	contraseña_cliente = models.CharField(max_length=128)
	es_admin = models.BooleanField(default=False)

	def __str__(self):
		return f"{self.nombre_cliente} {self.apellido_cliente}"

	class Meta:
		db_table = 'CLIENTE'


class Vehiculo(models.Model):
	vehiculo_id = models.AutoField(primary_key=True)
	usuario = models.ForeignKey(Cliente, db_column='usuario_id', on_delete=models.DO_NOTHING)
	patente = models.CharField(max_length=20, unique=True)
	marca = models.CharField(max_length=50, blank=True, null=True)
	modelo = models.CharField(max_length=50, blank=True, null=True)
	año = models.IntegerField(blank=True, null=True)

	class Meta:
		db_table = 'VEHICULO'
		managed = False

class Servicio(models.Model):
	servicio_id = models.AutoField(primary_key=True)
	nombre_servicio = models.CharField(max_length=100)
	descripcion_servicio = models.TextField()
	duracion_servicio = models.IntegerField()

	class Meta:
		db_table = 'SERVICIO'
		managed = False


class Reserva(models.Model):
	ESTADO_CHOICES = [
		('Pendiente', 'Pendiente'),
		('Confirmado', 'Confirmado'),
		('En Proceso', 'En Proceso'),
		('Completado', 'Completado'),
		('Cancelado', 'Cancelado'),
	]
	reserva_id = models.AutoField(primary_key=True)
	usuario = models.ForeignKey(Cliente, db_column='usuario_id', on_delete=models.DO_NOTHING)
	vehiculo = models.ForeignKey(Vehiculo, db_column='vehiculo_id', on_delete=models.DO_NOTHING)
	servicio = models.ForeignKey(Servicio, db_column='servicio_id', on_delete=models.DO_NOTHING)
	fecha_hora_inicio = models.DateTimeField()
	direccion_reserva = models.CharField(max_length=255, db_column='dirección_reserva')
	comuna_reserva = models.CharField(max_length=100, blank=True, null=True)
	notas_cliente = models.TextField(blank=True, null=True)
	estado_reserva = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='Pendiente')

	class Meta:
		db_table = 'RESERVA'
