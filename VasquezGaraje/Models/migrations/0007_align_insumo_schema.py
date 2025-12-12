from django.db import migrations


def align_insumo_schema(apps, schema_editor):
    connection = schema_editor.connection
    cursor = connection.cursor()

    def get_columns():
        cursor.execute("PRAGMA table_info('INSUMO')")
        return {row[1]: row for row in cursor.fetchall()}

    columns = get_columns()
    if not columns:
        return

    def rename_column(old, new):
        nonlocal columns
        if old in columns and new not in columns:
            cursor.execute(f"ALTER TABLE INSUMO RENAME COLUMN {old} TO {new}")
            columns = get_columns()

    rename_column("nombre_insumo", "nombre")
    rename_column("descripcion_insumo", "descripcion")
    rename_column("stock_actual", "cantidad")

    columns = get_columns()

    if "cantidad" not in columns:
        cursor.execute("ALTER TABLE INSUMO ADD COLUMN cantidad INTEGER DEFAULT 0")
        columns = get_columns()

    if "precio_unitario" not in columns:
        cursor.execute(
            "ALTER TABLE INSUMO ADD COLUMN precio_unitario DECIMAL(10,2) DEFAULT 0"
        )
        columns = get_columns()

    if "fecha_actualizacion" not in columns:
        cursor.execute(
            "ALTER TABLE INSUMO ADD COLUMN fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP"
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Models", "0006_insumo"),
    ]

    operations = [
        migrations.RunPython(align_insumo_schema, reverse_code=noop_reverse),
    ]
