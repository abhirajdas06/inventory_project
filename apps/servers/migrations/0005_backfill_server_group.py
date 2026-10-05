from django.db import migrations


def _infer(machine_type, model):
    # Frozen copy of apps.servers.groups.infer_server_group at the time of this
    # migration (migrations must not import live app code).
    mt = ' '.join(str(machine_type or '').upper().split())
    mo = ' '.join(str(model or '').upper().split())
    if mt == 'BLADE SERVER':
        return 'blade_server'
    if mt in ('CHASSIS', 'CHASISS', 'CHASIS'):
        return 'cisco_chassis' if 'CISCO' in mo else 'hp_ibm_dell_chassis'
    if mt == 'DESKTOP':
        return 'desktop'
    if mt in ('STORAGE', 'TAPE LIBRARY', 'LTO', 'TAPE DRIVE'):
        return 'storage'
    if mt == 'FIREWALL':
        return 'networking_firewall'
    if mt in ('ROUTER', 'MODEM'):
        return 'networking_router_modem'
    if mt == 'SWITCH':
        return 'networking_switch'
    if mo.startswith('SUN ') or any(h in mo for h in ('SPARC', 'NETRA', 'ORACLE')):
        return 'sun_servers'
    return 'rack_server'


def backfill(apps, schema_editor):
    Server = apps.get_model('servers', 'Server')
    for server in Server.objects.filter(group='').only('id', 'machine_type', 'model'):
        server.group = _infer(server.machine_type, server.model)
        server.save(update_fields=['group'])


class Migration(migrations.Migration):
    dependencies = [('servers', '0004_server_group')]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
