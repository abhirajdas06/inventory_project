from django.utils import timezone

from apps.core.models import ActivityLog, AssetTimelineEvent


def get_user_role(user):
    if not getattr(user, 'is_authenticated', False):
        return ''
    profile = getattr(user, 'profile', None)
    if profile:
        return profile.role
    if getattr(user, 'is_superuser', False):
        return 'ADMIN'
    return ''


def format_dated_remark(remark, when=None):
    text = (remark or '').strip()
    if not text:
        return ''
    stamp = (when or timezone.localdate()).isoformat()
    return f'{stamp} - {text}'


def append_dated_remark(existing, new_remark, when=None, separator='\n'):
    existing_text = (existing or '').strip()
    new_text = format_dated_remark(new_remark, when)
    if not new_text:
        return existing_text
    if not existing_text:
        return new_text
    return f'{existing_text}{separator}{new_text}'


def log_activity(
    *,
    action,
    module,
    entity='',
    entity_id='',
    user=None,
    barcode='',
    warehouse='',
    location='',
    old_values=None,
    new_values=None,
    remarks='',
    ip_address=None,
    metadata=None,
):
    return ActivityLog.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        role=get_user_role(user),
        action=action,
        module=module,
        entity=entity,
        entity_id=str(entity_id or ''),
        barcode=barcode or '',
        warehouse=warehouse or '',
        location=location or '',
        old_values=old_values or {},
        new_values=new_values or {},
        remarks=remarks or '',
        ip_address=ip_address,
        metadata=metadata or {},
    )


def log_timeline(
    *,
    product,
    event_type,
    user=None,
    warehouse='',
    location='',
    remarks='',
    details=None,
):
    return AssetTimelineEvent.objects.create(
        product=product,
        event_type=event_type,
        performed_by=user if getattr(user, 'is_authenticated', False) else None,
        warehouse=warehouse or '',
        location=location or '',
        remarks=remarks or '',
        details=details or {},
    )
