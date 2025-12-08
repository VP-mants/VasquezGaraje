from django import forms
from Models.models import Cliente

class RegistroForm(forms.ModelForm):
    contraseña_cliente = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input-auth', 'placeholder': 'Crea una contraseña segura'}),
        min_length=8,
        label="Contraseña",
    )
    confirmar_contraseña = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input-auth', 'placeholder': 'Repite la contraseña'}),
        min_length=8,
        label="Confirmar Contraseña",
    )

    class Meta:
        model = Cliente
        fields = ['nombre_cliente', 'apellido_cliente', 'correo_cliente', 'telefono_cliente', 'contraseña_cliente']

    def clean_correo_cliente(self):
        correo = self.cleaned_data.get('correo_cliente')
        if Cliente.objects.filter(correo_cliente=correo).exists():
            raise forms.ValidationError("Este correo ya está registrado.")
        return correo

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('contraseña_cliente')
        confirm = cleaned_data.get('confirmar_contraseña')
        if password and confirm and password != confirm:
            self.add_error('confirmar_contraseña', "Las contraseñas no coinciden.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'nombre_cliente': 'Ingresa tu nombre',
            'apellido_cliente': 'Ingresa tu apellido',
            'correo_cliente': 'correo@ejemplo.cl',
            'telefono_cliente': '+56 9 1234 5678',
        }
        for nombre, campo in self.fields.items():
            attrs = campo.widget.attrs
            attrs.setdefault('class', 'input-auth')
            if nombre in placeholders:
                attrs.setdefault('placeholder', placeholders[nombre])

class LoginForm(forms.Form):
    correo_cliente = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={'class': 'input-auth', 'placeholder': 'correo@ejemplo.cl'}),
    )
    contraseña_cliente = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'input-auth', 'placeholder': 'Ingresa tu contraseña'}),
        label="Contraseña",
    )


class CambiarContrasenaForm(forms.Form):
    contrasena_actual = forms.CharField(
        label="Contraseña actual",
        widget=forms.PasswordInput(attrs={'class': 'input-auth', 'placeholder': 'Ingresa tu contraseña actual'}),
    )
    nueva_contrasena = forms.CharField(
        label="Nueva contraseña",
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'input-auth', 'placeholder': 'Crea una nueva contraseña'}),
    )
    confirmar_contrasena = forms.CharField(
        label="Confirmar contraseña",
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'input-auth', 'placeholder': 'Repite la nueva contraseña'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        nueva = cleaned_data.get('nueva_contrasena')
        confirmar = cleaned_data.get('confirmar_contrasena')
        if nueva and confirmar and nueva != confirmar:
            self.add_error('confirmar_contrasena', 'Las contraseñas no coinciden.')
        return cleaned_data
