from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0007_alter_assettimelineevent_event_type')]

    operations = [
        migrations.CreateModel(
            name='RolePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('ADMIN', 'Admin'), ('STOCK_IN', 'Stock In User'), ('STOCK_OUT', 'Stock Out User'), ('AUDIT', 'Audit User')], max_length=20, unique=True)),
                ('permissions', models.JSONField(blank=True, default=list)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
