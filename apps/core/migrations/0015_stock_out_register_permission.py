from django.db import migrations

ROLES = ('ADMIN', 'AUDIT', 'READONLY_OUT')


def grant(apps, schema_editor):
    # New 'stock_out_register' permission is on by default for Admin, Audit User
    # and Read-only: Out Stock. Add it to those roles if they were customised.
    RolePermission = apps.get_model('core', 'RolePermission')
    for row in RolePermission.objects.filter(role__in=ROLES):
        if 'stock_out_register' not in (row.permissions or []):
            row.permissions = list(row.permissions or []) + ['stock_out_register']
            row.save(update_fields=['permissions'])


def revoke(apps, schema_editor):
    RolePermission = apps.get_model('core', 'RolePermission')
    for row in RolePermission.objects.all():
        perms = [p for p in (row.permissions or []) if p != 'stock_out_register']
        if perms != list(row.permissions or []):
            row.permissions = perms
            row.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_delete_inventory_permission'),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
