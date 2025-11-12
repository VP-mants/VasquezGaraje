from django import forms
from Models.models import Reserva, Vehiculo, Servicio

class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ['vehiculo', 'servicio', 'fecha_hora_inicio', 'direccion_reserva', 'comuna_reserva']
        widgets = {
            'fecha_hora_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
