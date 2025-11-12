import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','Project_Config.settings')
import django
django.setup()
from Models.models import Cliente
from django.contrib.auth.hashers import make_password

count=0
for c in Cliente.objects.all():
    pwd = c.contraseña_cliente or ''
    if pwd and '$' not in pwd:
        c.contraseña_cliente = make_password(pwd)
        c.save()
        count+=1
print(f'Hashed {count} passwords')
