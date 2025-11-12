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
