from django import forms
from .models import Cliente

class RegistroForm(forms.ModelForm):
    contraseña_cliente = forms.CharField(widget=forms.PasswordInput, min_length=8, label="Contraseña")
    confirmar_contraseña = forms.CharField(widget=forms.PasswordInput, min_length=8, label="Confirmar Contraseña")

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

class LoginForm(forms.Form):
    correo_cliente = forms.EmailField(label="Correo electrónico")
    contraseña_cliente = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
