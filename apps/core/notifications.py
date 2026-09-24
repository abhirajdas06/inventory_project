"""Recipient lookup and failure-alert emails.

Recipients live in the ReportRecipient table (editable in the Django admin).
If the table has no active rows for a kind we fall back to the env/settings
lists so mail never silently goes nowhere.
"""
import logging
import traceback

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_ERRORS_IN_MAIL = 100


def get_recipients(kind):
    from apps.core.models import ReportRecipient

    emails = list(
        ReportRecipient.objects.filter(kind=kind, is_active=True)
        .order_by('email').values_list('email', flat=True)
    )
    if emails:
        return emails
    fallback = 'DAILY_REPORT_RECIPIENTS' if kind == 'DAILY_REPORT' else 'FAILURE_ALERT_RECIPIENTS'
    return list(getattr(settings, fallback, []) or [])


def send_failure_alert(subject, body):
    """Email a failure explanation. NEVER raises — an alert problem must not
    mask the original failure. Returns True if a mail was handed to the backend."""
    try:
        recipients = get_recipients('FAILURE_ALERT')
        if not recipients:
            logger.error('Failure alert not sent (no recipients): %s', subject)
            return False
        EmailMessage(
            subject=f'[InvenTrack] {subject}',
            body=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=recipients,
        ).send(fail_silently=False)
        return True
    except Exception:
        logger.exception('Could not send failure alert: %s', subject)
        return False


def send_import_failure_email(job, reason=None):
    """Explain why an import failed / had failing rows."""
    from apps.core.importers import IMPORT_LABELS

    label = IMPORT_LABELS.get(job.model_key, job.model_key)
    file_name = job.upload.name.rsplit('/', 1)[-1] if job.upload else ''
    user = job.created_by.get_username() if job.created_by else 'unknown'
    errors = list(job.errors or [])

    lines = [
        f'Import #{job.id} ({label}) did not import cleanly.',
        '',
        f'File:        {file_name}',
        f'Uploaded by: {user}',
        f'Warehouse:   {job.store_location}',
        f'When:        {timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")}',
        f'Status:      {job.status}',
        f'Rows:        {job.total_rows} total, {job.success_count} imported, {job.error_count} failed',
    ]
    if reason:
        lines += ['', f'Reason: {reason}']
    if errors:
        shown = errors[-MAX_ERRORS_IN_MAIL:]
        lines += ['', f'Row errors (Excel row number -> why), showing {len(shown)} of {job.error_count}:']
        lines += [f'  Row {e.get("row")}: {e.get("error")}' for e in shown]
        if job.error_count > len(shown):
            lines.append(f'  ... {job.error_count - len(shown)} earlier errors not kept.')
    lines += ['', 'Rows that are not listed above were imported successfully.',
              'Fix the listed rows in the Excel and re-upload only those rows.']
    return send_failure_alert(f'Import failed: {label} (job #{job.id})', '\n'.join(lines))


def send_job_failure_email(job_name, exc):
    """Explain why a scheduled job (nightly export / mail) crashed."""
    body = (
        f'The scheduled job "{job_name}" failed at '
        f'{timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")}.\n\n'
        f'Error: {exc.__class__.__name__}: {exc}\n\n'
        f'Traceback:\n{"".join(traceback.format_exception(type(exc), exc, exc.__traceback__))}'
    )
    return send_failure_alert(f'Scheduled job failed: {job_name}', body)
