from django.db import migrations


def grant(apps, schema_editor):
    # New 'staff_activity' permission (Employee Activity on the dashboard) is
    # on by default for Admin only. Add it there if Admin was customised.
    RolePermission = apps.get_model('core', 'RolePermission')
    row = RolePermission.objects.filter(role='ADMIN').first()
    if row and 'staff_activity' not in (row.permissions or []):
        row.permissions = list(row.permissions or []) + ['staff_activity']
        row.save(update_fields=['permissions'])


def revoke(apps, schema_editor):
    RolePermission = apps.get_model('core', 'RolePermission')
    for row in RolePermission.objects.all():
        perms = [p for p in (row.permissions or []) if p != 'staff_activity']
        if perms != list(row.permissions or []):
            row.permissions = perms
            row.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_stock_out_register_permission'),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
