"""Employee activity — how many inventory transactions (stock in, stock out,
audit, transfer) each user performed in a month, and the transactions themselves.

* Stock in / stock out / audit: the user recorded as having performed the
  transaction (for audits recorded before `performed_by` was always set, the
  auditor).
* Transfer: each item put on a transfer request (counted for the requester, on
  the day it was requested) and each item received (counted for the receiver,
  on the day it was received). Receiving also writes a stock-in record; that one
  is counted as the transfer receipt, not again as a stock in.

Months are calendar months in the site's time zone.
"""
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, DateTimeField, Exists, ExpressionWrapper, F, OuterRef, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.permissions import require_permission, role_label
from apps.inventory.models import InventoryTransaction, InventoryTransfer, TransferRequestItem

TYPES = [('IN', 'Stock In'), ('OUT', 'Stock Out'), ('AUDIT', 'Audit'), ('TRANSFER', 'Transfer')]
TXN_TYPES = ('IN', 'OUT', 'AUDIT')
COUNT_KEYS = ('n_in', 'n_out', 'n_audit', 'n_transfer', 'total')
_BARCODE_ATTRS = ('spare', 'card', 'cpu', 'controller', 'memory', 'sfp', 'railkit', 'harddisk', 'networking_spare', 'server')


def parse_month(value):
    """'2026-11' -> first day of that month (a date). Default / future: this month."""
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


# ── querysets ──────────────────────────────────────────────────────────────

def _stock_transactions():
    """Stock in / out / audit records with the acting user, leaving out the
    stock-in that receiving a transfer writes (that is counted as a transfer)."""
    window = timedelta(seconds=10)
    receipt = InventoryTransfer.objects.filter(
        product=OuterRef('product'),
        transferred_by=OuterRef('performed_by'),
        created_at__gte=ExpressionWrapper(OuterRef('created_at') - window, output_field=DateTimeField()),
        created_at__lte=ExpressionWrapper(OuterRef('created_at') + window, output_field=DateTimeField()),
    )
    return (InventoryTransaction.objects.filter(transaction_type__in=TXN_TYPES)
            .annotate(actor_id=Coalesce('performed_by_id', 'audited_by_id'))
            .annotate(is_transfer_receipt=Exists(receipt))
            .exclude(transaction_type='IN', is_transfer_receipt=True))


def _in_month(qs, field, start, end):
    return qs.filter(**{f'{field}__gte': start, f'{field}__lt': end})


def _transfer_requested(start, end):
    return _in_month(TransferRequestItem.objects.all(), 'request__created_at', start, end)


def _transfer_received(start, end):
    return _in_month(TransferRequestItem.objects.filter(received_at__isnull=False), 'received_at', start, end)


def _counts_for(start, end, user_id=None):
    """{user_id: {n_in, n_out, n_audit, n_transfer, total}} for the month
    (one user only when user_id is given)."""
    txns = _in_month(_stock_transactions(), 'created_at', start, end)
    requested = _transfer_requested(start, end)
    received = _transfer_received(start, end)
    if user_id is not None:
        txns = txns.filter(actor_id=user_id)
        requested = requested.filter(request__requested_by_id=user_id)
        received = received.filter(received_by_id=user_id)

    result = {}

    def bucket(uid):
        return result.setdefault(uid, dict.fromkeys(COUNT_KEYS, 0))

    for row in txns.values('actor_id').annotate(
            n_in=Count('id', filter=Q(transaction_type='IN')),
            n_out=Count('id', filter=Q(transaction_type='OUT')),
            n_audit=Count('id', filter=Q(transaction_type='AUDIT'))).order_by():
        b = bucket(row['actor_id'])
        for key in ('n_in', 'n_out', 'n_audit'):
            b[key] += row[key]
    for uid_field, qs in (('request__requested_by_id', requested), ('received_by_id', received)):
        for row in qs.values(uid_field).annotate(n=Count('id')).order_by():
            bucket(row[uid_field])['n_transfer'] += row['n']
    for b in result.values():
        b['total'] = b['n_in'] + b['n_out'] + b['n_audit'] + b['n_transfer']
    return result


# ── dashboard summary ─────────────────────────────────────────────────────

def month_summary(first):
    """One row per active user (plus anyone who did something this month),
    busiest first, and a count of records with no user recorded."""
    start, end = month_bounds(first)
    by_user = _counts_for(start, end)
    empty = dict.fromkeys(COUNT_KEYS, 0)
    users = User.objects.select_related('profile').filter(Q(is_active=True) | Q(id__in=[k for k in by_user if k]))
    table = []
    for user in users:
        profile = getattr(user, 'profile', None)
        role = profile.role if profile else ('ADMIN' if user.is_superuser else '')
        table.append({
            'user': user,
            'name': user.get_full_name() or user.get_username(),
            'role': role_label(role) if role else '',
            **by_user.get(user.id, empty),
        })
    table.sort(key=lambda r: (-r['total'], r['name'].lower()))
    unassigned = by_user.get(None, empty)
    return {
        'rows': table,
        'unassigned': unassigned['total'],
        'totals': {k: sum(r[k] for r in table) + unassigned[k] for k in COUNT_KEYS},
    }


# ── one employee ───────────────────────────────────────────────────────────

def _barcode(product):
    for attr in _BARCODE_ATTRS:
        try:
            obj = getattr(product, attr)
        except Exception:
            obj = None
        if obj is not None and getattr(obj, 'barcode', None):
            return obj.barcode
    return ''


def _txn_row(t):
    return {
        'when': t.created_at,
        'kind': t.transaction_type,
        'kind_label': t.get_transaction_type_display(),
        'status': t.get_stock_status_display(),
        'product': t.product,
        'barcode': _barcode(t.product),
        'store': t.store_location,
        'client': t.client_name or '',
        'invoice': t.invoice_no or '',
        'olf_dc': t.olf_dc_number or '',
        'remark': t.audit_remark or '',
    }


def _transfer_row(item, received):
    tr = item.request
    locations = ' → '.join(filter(None, [item.source_location, item.destination_location if received else '']))
    return {
        'when': item.received_at if received else tr.created_at,
        'kind': 'TRANSFER',
        'kind_label': 'Transfer Received' if received else 'Transfer Requested',
        'status': f'TR-{tr.id}',
        'product': item.product,
        'barcode': item.barcode or _barcode(item.product),
        'store': f'{tr.source_warehouse} → {tr.destination_warehouse}',
        'client': '', 'invoice': '', 'olf_dc': '',
        'remark': locations,
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

    counts = _counts_for(start, end, employee.id).get(employee.id, dict.fromkeys(COUNT_KEYS, 0))

    # Light (timestamp, kind, id) list across all three sources, sorted and
    # paginated; only the rows on the current page are then loaded in full.
    events = []
    if tx_type in ('', 'IN', 'OUT', 'AUDIT'):
        txns = _in_month(_stock_transactions(), 'created_at', start, end).filter(actor_id=employee.id)
        if tx_type:
            txns = txns.filter(transaction_type=tx_type)
        events += [(when, 't', pk) for when, pk in txns.values_list('created_at', 'id')]
    if tx_type in ('', 'TRANSFER'):
        events += [(when, 'req', pk) for when, pk in _transfer_requested(start, end)
                   .filter(request__requested_by_id=employee.id).values_list('request__created_at', 'id')]
        events += [(when, 'rcv', pk) for when, pk in _transfer_received(start, end)
                   .filter(received_by_id=employee.id).values_list('received_at', 'id')]
    events.sort(key=lambda e: (e[0], e[2]), reverse=True)

    paginator = Paginator(events, 100)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    page_events = list(page_obj.object_list)
    related = ['product__category'] + [f'product__{attr}' for attr in _BARCODE_ATTRS]
    txn_map = InventoryTransaction.objects.select_related(*related).in_bulk([e[2] for e in page_events if e[1] == 't'])
    item_map = TransferRequestItem.objects.select_related('request', *related).in_bulk(
        [e[2] for e in page_events if e[1] != 't'])
    rows = []
    for _, kind, pk in page_events:
        if kind == 't' and pk in txn_map:
            rows.append(_txn_row(txn_map[pk]))
        elif kind != 't' and pk in item_map:
            rows.append(_transfer_row(item_map[pk], received=(kind == 'rcv')))

    # Last 12 months, newest first — each links to that month's list.
    months = []
    this_month = timezone.localdate().replace(day=1)
    for step in range(12):
        m = shift_month(this_month, -step)
        m_counts = _counts_for(*month_bounds(m), employee.id).get(employee.id, dict.fromkeys(COUNT_KEYS, 0))
        months.append({'month': m, 'value': m.strftime('%Y-%m'), **m_counts})

    return render(request, 'core/staff_activity_detail.html', {
        'employee': employee,
        'employee_name': employee.get_full_name() or employee.get_username(),
        'counts': counts,
        'tx_type': tx_type,
        'page_obj': page_obj,
        'rows': rows,
        'months': months,
        **month_nav(first),
    })
