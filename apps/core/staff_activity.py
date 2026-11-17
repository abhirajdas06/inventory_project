"""Employee activity — how many inventory transactions (stock in, stock out,
audit) each user performed in a month, and the transactions themselves.

A transaction belongs to the user recorded as having performed it (for audits
recorded before `performed_by` was always set, the auditor). Months are
calendar months in the site's time zone.
"""
from datetime import datetime

from django.contrib.auth.models import User
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, F, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.permissions import require_permission, role_label
from apps.inventory.models import InventoryTransaction

TYPES = [('IN', 'Stock In'), ('OUT', 'Stock Out'), ('AUDIT', 'Audit')]
_BARCODE_ATTRS = ('spare', 'card', 'cpu', 'controller', 'memory', 'sfp', 'railkit', 'harddisk', 'networking_spare', 'server')


def parse_month(value):
    """'2026-11' -> (first day of that month as a date). Default: this month."""
    today = timezone.localdate()
    try:
        year, month = (int(part) for part in str(value or '').split('-')[:2])
        first = datetime(year, month, 1).date()
    except (TypeError, ValueError):
        first = today.replace(day=1)
    return min(first, today.replace(day=1))


def shift_month(first, step):
    month_index = first.year * 12 + first.month - 1 + step
    return first.replace(year=month_index // 12, month=month_index % 12 + 1, day=1)


def month_bounds(first):
    """Aware datetimes [start, end) covering the calendar month."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime(first.year, first.month, 1), tz)
    nxt = shift_month(first, 1)
    end = timezone.make_aware(datetime(nxt.year, nxt.month, 1), tz)
    return start, end


def month_nav(first):
    this_month = timezone.localdate().replace(day=1)
    return {
        'month': first,
        'month_value': first.strftime('%Y-%m'),
        'prev_month': shift_month(first, -1).strftime('%Y-%m'),
        'next_month': shift_month(first, 1).strftime('%Y-%m') if first < this_month else '',
        'max_month': this_month.strftime('%Y-%m'),
    }


def _with_actor(qs):
    return qs.annotate(actor_id=Coalesce('performed_by_id', 'audited_by_id'))


def _type_counts():
    return {f'n_{key.lower()}': Count('id', filter=Q(transaction_type=key)) for key, _ in TYPES}


def month_summary(first):
    """One row per active user (plus anyone who did something this month),
    busiest first, and a row for transactions with no user recorded."""
    start, end = month_bounds(first)
    rows = (_with_actor(InventoryTransaction.objects.filter(created_at__gte=start, created_at__lt=end))
            .values('actor_id').annotate(total=Count('id'), **_type_counts()))
    by_user = {r['actor_id']: r for r in rows}
    users = User.objects.select_related('profile').filter(Q(is_active=True) | Q(id__in=[k for k in by_user if k]))
    empty = {'total': 0, **{f'n_{key.lower()}': 0 for key, _ in TYPES}}
    table = []
    for user in users:
        counts = by_user.get(user.id, empty)
        profile = getattr(user, 'profile', None)
        role = profile.role if profile else ('ADMIN' if user.is_superuser else '')
        table.append({
            'user': user,
            'name': user.get_full_name() or user.get_username(),
            'role': role_label(role) if role else '',
            **{k: counts[k] for k in empty},
        })
    table.sort(key=lambda r: (-r['total'], r['name'].lower()))
    unassigned = by_user.get(None)
    return {
        'rows': table,
        'unassigned': unassigned['total'] if unassigned else 0,
        'totals': {k: sum(r[k] for r in table) + (unassigned[k] if unassigned else 0) for k in empty},
    }


@require_permission('staff_activity')
def staff_activity_detail(request, user_id):
    """One employee's transactions for a month, with a month-by-month summary."""
    employee = get_object_or_404(User, id=user_id)
    first = parse_month(request.GET.get('month'))
    start, end = month_bounds(first)
    tx_type = (request.GET.get('type') or '').upper()
    if tx_type not in dict(TYPES):
        tx_type = ''

    mine = _with_actor(InventoryTransaction.objects.all()).filter(actor_id=employee.id)
    month_qs = mine.filter(created_at__gte=start, created_at__lt=end)
    counts = month_qs.aggregate(total=Count('id'), **_type_counts())

    listing = month_qs.filter(transaction_type=tx_type) if tx_type else month_qs
    listing = listing.select_related('product', 'product__category').annotate(
        barcode=Coalesce(*[F(f'product__{attr}__barcode') for attr in _BARCODE_ATTRS]),
    ).order_by('-created_at', '-id')
    paginator = Paginator(listing, 100)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    # Last 12 months, newest first — each links to that month's list.
    months = []
    this_month = timezone.localdate().replace(day=1)
    for step in range(12):
        m = shift_month(this_month, -step)
        m_start, m_end = month_bounds(m)
        c = mine.filter(created_at__gte=m_start, created_at__lt=m_end).aggregate(total=Count('id'), **_type_counts())
        months.append({'month': m, 'value': m.strftime('%Y-%m'), **c})

    return render(request, 'core/staff_activity_detail.html', {
        'employee': employee,
        'employee_name': employee.get_full_name() or employee.get_username(),
        'counts': counts,
        'types': TYPES,
        'tx_type': tx_type,
        'page_obj': page_obj,
        'transactions': page_obj.object_list,
        'months': months,
        **month_nav(first),
    })
