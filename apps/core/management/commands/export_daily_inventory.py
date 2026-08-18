from django.core.management.base import BaseCommand

from apps.core.reporting import export_daily_inventory_snapshots


class Command(BaseCommand):
    help = 'Export daily live and stocked-out inventory snapshots to Excel files.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            default=None,
            help='Optional base directory for export files.',
        )

    def handle(self, *args, **options):
        outputs = export_daily_inventory_snapshots(output_dir=options['output_dir'])
        self.stdout.write(self.style.SUCCESS(
            f"Exported live inventory to {outputs['live']} and stocked-out inventory to {outputs['stocked_out']}"
        ))
