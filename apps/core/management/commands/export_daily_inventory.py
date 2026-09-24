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
            help='Email the workbooks to the active daily-report recipients (Admin Panel -> Report recipients).',
        )
        parser.add_argument(
            '--recipients',
            default=None,
            help='Comma-separated recipient override (otherwise uses the Report recipients configured in the admin).',
        )

    def handle(self, *args, **options):
        from apps.core.notifications import send_job_failure_email

        try:
            outputs = self._run(options)
        except Exception as exc:
            # Tell the alert recipients WHY, then fail loudly so cron/systemd
            # also records a non-zero exit.
            alerted = send_job_failure_email('export_daily_inventory', exc)
            self.stderr.write(self.style.ERROR(
                f'Daily export failed: {exc} (failure alert {"sent" if alerted else "NOT sent"})'
            ))
            raise
        self.stdout.write(self.style.SUCCESS(
            f"Exported live inventory to {outputs['live']} and "
            f"stocked-out inventory to {outputs['stocked_out']}"
        ))

    def _run(self, options):
        if not options['email']:
            return export_daily_inventory_snapshots(output_dir=options['output_dir'])
        recipients = None
        if options['recipients']:
            recipients = [r.strip() for r in options['recipients'].split(',') if r.strip()]
        result = send_daily_inventory_email(
            recipients=recipients,
            output_dir=options['output_dir'],
        )
        if result.get('sent'):
            self.stdout.write(self.style.SUCCESS(
                f"Emailed daily inventory to: {', '.join(result['recipients'])}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Files exported but not emailed: {result.get('reason')}"
            ))
        return result['outputs']
