from django.db import migrations

DEFAULTS = [
    ('abhiraj@zacocomputer.com', 'Abhiraj', 'DAILY_REPORT'),
    ('nazim@zacocomputer.com', 'Nazim', 'DAILY_REPORT'),
    ('abhiraj@zacocomputer.com', 'Abhiraj', 'FAILURE_ALERT'),
]


def seed(apps, schema_editor):
    ReportRecipient = apps.get_model('core', 'ReportRecipient')
    for email, name, kind in DEFAULTS:
        ReportRecipient.objects.get_or_create(email=email, kind=kind, defaults={'name': name})


class Migration(migrations.Migration):
    dependencies = [('core', '0010_reportrecipient')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
