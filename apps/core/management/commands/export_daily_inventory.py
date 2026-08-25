from django.core.management.base import BaseCommand

from apps.core.reporting import (
    export_daily_inventory_snapshots,
    send_daily_inventory_email,
)


class Command(BaseCommand):
    help = 'Export daily live and stocked-out inventory snapshots to Excel, optionally emailing them.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            default=None,
            help='Optional base directory for export files.',
        )
        parser.add_argument(
            '--email',
            action='store_true',
            help='Email the workbooks to DAILY_REPORT_RECIPIENTS after exporting.',
        )
        parser.add_argument(
            '--recipients',
            default=None,
            help='Comma-separated recipient override (otherwise uses settings.DAILY_REPORT_RECIPIENTS).',
        )

    def handle(self, *args, **options):
        if options['email']:
            recipients = None
            if options['recipients']:
                recipients = [r.strip() for r in options['recipients'].split(',') if r.strip()]
            result = send_daily_inventory_email(
                recipients=recipients,
                output_dir=options['output_dir'],
            )
            outputs = result['outputs']
            if result.get('sent'):
                self.stdout.write(self.style.SUCCESS(
                    f"Emailed daily inventory to: {', '.join(result['recipients'])}"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Files exported but not emailed: {result.get('reason')}"
                ))
        else:
            outputs = export_daily_inventory_snapshots(output_dir=options['output_dir'])

        self.stdout.write(self.style.SUCCESS(
            f"Exported live inventory to {outputs['live']} and "
            f"stocked-out inventory to {outputs['stocked_out']}"
        ))
