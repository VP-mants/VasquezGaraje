from datetime import datetime, timedelta, time

from django import forms
from django.db import connection
from django.db.models import Case, IntegerField, Value, When
from django.db.utils import OperationalError, ProgrammingError

from Models.models import Reserva, Servicio

_SERVICIO_CATEGORIA_LISTO = False

_SERVICIOS_PREDETERMINADOS = (
    {
        'nombre_servicio': 'Diagnóstico General',
        'descripcion_servicio': 'Evaluación inicial para determinar el problema del vehículo.',
        'duracion_servicio': 90,
        'categoria': Servicio.CATEGORIA_CONSULTA,
    },
    {
        'nombre_servicio': 'Especificar Reparación',
        'descripcion_servicio': 'Revisión y ajuste del sistema de frenos y componentes asociados.',
        'duracion_servicio': 90,
        'categoria': Servicio.CATEGORIA_REPARACION,
    },
    {
        'nombre_servicio': 'Servicio Personalizado',
        'descripcion_servicio': 'Describe el servicio requerido en las notas para coordinar los detalles.',
        'duracion_servicio': 90,
        'categoria': Servicio.CATEGORIA_OTROS,
    },
)


def get_servicios_ordenados():
    orden_categoria = Case(
        When(categoria=Servicio.CATEGORIA_CONSULTA, then=Value(0)),
        When(categoria=Servicio.CATEGORIA_REPARACION, then=Value(1)),
        When(categoria=Servicio.CATEGORIA_OTROS, then=Value(2)),
        default=Value(99),
        output_field=IntegerField(),
    )
    return Servicio.objects.all().annotate(_categoria_orden=orden_categoria).order_by(
        '_categoria_orden', 'nombre_servicio'
    )


def ensure_servicio_categoria_column():
    """Agrega la columna categoria a SERVICIO si aún no existe."""
    global _SERVICIO_CATEGORIA_LISTO
    if _SERVICIO_CATEGORIA_LISTO:
        return

    tabla = Servicio._meta.db_table
    try:
        with connection.cursor() as cursor:
            columnas = [col.name.lower() for col in connection.introspection.get_table_description(cursor, tabla)]
            if 'categoria' not in columnas:
                valor_default = Servicio.CATEGORIA_OTROS.replace("'", "''")
                cursor.execute(
                    f"ALTER TABLE \"{tabla}\" ADD COLUMN categoria VARCHAR(30) DEFAULT '{valor_default}'"
                )
                cursor.execute(
                    f"UPDATE \"{tabla}\" SET categoria = '{valor_default}' "
                    "WHERE categoria IS NULL OR TRIM(categoria) = ''"
                )
    except (OperationalError, ProgrammingError):
        return

    _SERVICIO_CATEGORIA_LISTO = True


def ensure_servicios_predeterminados():
    if Servicio.objects.exists():
        return

    try:
        for datos in _SERVICIOS_PREDETERMINADOS:
            Servicio.objects.get_or_create(
                nombre_servicio=datos['nombre_servicio'],
                defaults={
                    'descripcion_servicio': datos['descripcion_servicio'],
                    'duracion_servicio': datos['duracion_servicio'],
                    'categoria': datos['categoria'],
                },
            )
    except (OperationalError, ProgrammingError):
        return


RESERVA_DURACION_MINUTOS = 90
RESERVA_SLOT_STEP_MINUTOS = 90
RESERVA_HORA_INICIO = time(10, 0)
RESERVA_HORA_FIN = time(18, 30)


class ReservaForm(forms.ModelForm):
    vehiculo_texto = forms.CharField(
        label='Vehículo',
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'input-box', 'placeholder': 'Ej: Toyota Corolla 2018'},
        ),
    )

    servicio = forms.ModelChoiceField(
        label='Servicio',
        queryset=Servicio.objects.none(),
        widget=forms.Select(attrs={'class': 'input-box'}),
        empty_label='Selecciona un servicio',
    )

    fecha_reserva = forms.DateField(
        label='Fecha',
        required=True,
        widget=forms.DateInput(attrs={'class': 'input-box', 'type': 'date'}),
    )

    hora_reserva = forms.ChoiceField(
        label='Horario',
        required=True,
        choices=(),
        widget=forms.Select(attrs={'class': 'input-box'}),
    )

    class Meta:
        model = Reserva
        # Excluimos usuario, estado_reserva y vehiculo, que se asignan manualmente
        fields = [
            'servicio',
            'fecha_hora_inicio',
            'direccion_reserva',
            'comuna_reserva',
            'patente',
            'notas_cliente',
        ]
        widgets = {
            'fecha_hora_inicio': forms.HiddenInput(),
            'direccion_reserva': forms.TextInput(attrs={'class': 'input-box'}),
            'comuna_reserva': forms.TextInput(attrs={'class': 'input-box'}),
            'patente': forms.TextInput(
                attrs={'class': 'input-box', 'placeholder': 'Ej: AB123CD'},
            ),
            'notas_cliente': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Notas adicionales (opcional)', 'class': 'input-box'},
            ),
        }

    field_order = [
        'vehiculo_texto',
        'servicio',
        'fecha_reserva',
        'hora_reserva',
        'fecha_hora_inicio',
        'direccion_reserva',
        'comuna_reserva',
        'patente',
        'notas_cliente',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(self.field_order)
        self.fields['fecha_hora_inicio'].required = False
        self.fields['hora_reserva'].choices = self._generar_slot_choices()
        if self.instance and getattr(self.instance, 'vehiculo_id', None):
            self.fields['vehiculo_texto'].initial = str(self.instance.vehiculo)
        ensure_servicio_categoria_column()
        ensure_servicios_predeterminados()
        servicios_disponibles = get_servicios_ordenados()
        self.fields['servicio'].queryset = servicios_disponibles
        self.fields['servicio'].label_from_instance = (
            lambda obj: f"{obj.get_categoria_display()} · {obj.nombre_servicio}"
        )
        self.fields['patente'].required = True

        if not self.is_bound:
            fecha_inicial = None
            hora_inicial = None

            if self.initial.get('fecha_reserva') and self.initial.get('hora_reserva'):
                fecha_inicial = self.initial['fecha_reserva']
                hora_inicial = self.initial['hora_reserva']
            elif self.initial.get('fecha_hora_inicio'):
                fecha_inicial, hora_inicial = self._descomponer_datetime(self.initial['fecha_hora_inicio'])
            elif getattr(self.instance, 'fecha_hora_inicio', None):
                fecha_inicial, hora_inicial = self._descomponer_datetime(self.instance.fecha_hora_inicio)

            if fecha_inicial:
                self.initial.setdefault('fecha_reserva', fecha_inicial)
            if hora_inicial:
                self.initial.setdefault('hora_reserva', hora_inicial)

    @staticmethod
    def _generar_slot_choices():
        puntos = []
        cursor = datetime.combine(datetime.today(), RESERVA_HORA_INICIO)
        fin = datetime.combine(datetime.today(), RESERVA_HORA_FIN)
        paso = timedelta(minutes=RESERVA_SLOT_STEP_MINUTOS)
        duracion = timedelta(minutes=RESERVA_DURACION_MINUTOS)

        while cursor.time() <= RESERVA_HORA_FIN:
            inicio_str = cursor.strftime('%H:%M')
            fin_str = (cursor + duracion).strftime('%H:%M')
            puntos.append((inicio_str, f"{inicio_str} - {fin_str}"))
            cursor += paso
        return puntos

    @staticmethod
    def _descomponer_datetime(valor):
        if not valor:
            return None, None
        if hasattr(valor, 'tzinfo') and valor.tzinfo is not None:
            from django.utils import timezone

            valor = timezone.localtime(valor)
        return valor.date(), valor.strftime('%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha_reserva')
        hora = cleaned_data.get('hora_reserva')

        if fecha and hora:
            try:
                hora_obj = datetime.strptime(hora, '%H:%M').time()
            except ValueError:
                self.add_error('hora_reserva', 'Selecciona un horario válido.')
            else:
                cleaned_data['fecha_hora_inicio'] = datetime.combine(fecha, hora_obj)

        return cleaned_data
