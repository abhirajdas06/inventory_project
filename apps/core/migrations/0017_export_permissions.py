from django.db import migrations

EXPORT_PERMS = ('export_live', 'export_sold', 'export_faulty', 'export_stock_out_register', 'export_audit')


def grant(apps, schema_editor):
    """Exports now have their own permissions. A role customised in Role
    Settings keeps exactly the exports it could already do:
      reports                     -> export live, sold, faulty
      sold_view                   -> export sold, faulty
      stock_out_register          -> export Stock Out Register
      audit_view                  -> export Audit Report
    """
    RolePermission = apps.get_model('core', 'RolePermission')
    for row in RolePermission.objects.all():
        perms = set(row.permissions or [])
        add = set()
        if 'reports' in perms:
            add |= {'export_live', 'export_sold', 'export_faulty'}
        if 'sold_view' in perms:
            add |= {'export_sold', 'export_faulty'}
        if 'stock_out_register' in perms:
            add.add('export_stock_out_register')
        if 'audit_view' in perms:
            add.add('export_audit')
        if add - perms:
            row.permissions = list(row.permissions or []) + sorted(add - perms)
            row.save(update_fields=['permissions'])


def revoke(apps, schema_editor):
    RolePermission = apps.get_model('core', 'RolePermission')
    for row in RolePermission.objects.all():
        perms = [p for p in (row.permissions or []) if p not in EXPORT_PERMS]
        if perms != list(row.permissions or []):
            row.permissions = perms
            row.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_staff_activity_permission'),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
