from django import forms
from Models.models import Reserva, Vehiculo, Servicio

class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        # Excluimos usuario y estado_reserva, que se asignan automáticamente
        fields = [
            'vehiculo',
            'servicio',
            'fecha_hora_inicio',
            'direccion_reserva',
            'comuna_reserva',
            'notas_cliente',
        ]
        widgets = {
            'vehiculo': forms.Select(attrs={'class': 'input-box'}),
            'servicio': forms.Select(attrs={'class': 'input-box'}),
            'fecha_hora_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'input-box'}),
            'direccion_reserva': forms.TextInput(attrs={'class': 'input-box'}),
            'comuna_reserva': forms.TextInput(attrs={'class': 'input-box'}),
            'notas_cliente': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Notas adicionales (opcional)', 'class': 'input-box'}),
        }
