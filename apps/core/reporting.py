from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


def _clean_cell(value):
    """openpyxl cannot write timezone-aware datetimes — strip the tzinfo
    (converting to local time first) so exports don't blow up with real data."""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return timezone.localtime(value).replace(tzinfo=None)
    return value


def _append_row(ws, values):
    ws.append([_clean_cell(v) for v in values])


def _safe_sheet_name(name):
    cleaned = ''.join(ch for ch in name if ch.isalnum() or ch in (' ', '_', '-')).strip()
    cleaned = cleaned[:31].strip()
    return cleaned or 'Sheet'


def _resolve_attr(obj, path):
    current = obj
    for part in path.split('.'):
        current = getattr(current, part, None)
        if current is None:
            return ''
    return current


def _style_header(ws):
    fill = PatternFill(fill_type='solid', fgColor='DCEBFF')
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = fill


# Every sheet in the nightly workbooks uses the EXACT column headers of the
# matching import template, so the file can be uploaded straight back through
# Import (pick the category; the importer reads the sheet with that name).
# key = import key, value = key used in categories.views.LIST_MODELS
SIMPLE_EXPORT_KEYS = {
    'battery': 'spare',
    'card': 'card',
    'cpu': 'cpu',
    'harddisk': 'harddisk',
    'memory': 'memory',
    'networking_spare': 'networking_spare',
    'railkit': 'railkit',
    'sfp': 'sfp',
}


def _out_details(product):
    """(client, invoice, olf/dc, status, out date) of a product's latest
    stock-out — the 5 appended Stock Out import columns."""
    from apps.inventory.models import InventoryTransaction

    txn = (InventoryTransaction.objects
           .filter(product=product, transaction_type='OUT')
           .order_by('-created_at').first()) if product else None
    if not txn:
        return ['', '', '', '', '']
    return [txn.client_name or '', txn.invoice_no or '', txn.olf_dc_number or '',
            txn.stock_status or '', txn.stock_out_date or '']


def _import_cell(item, target, sold):
    if target == 'category':
        return item.product.category.name if item.product and item.product.category else ''
    if target == 'serial_no':
        return item.product.serial_no if item.product else ''
    if target == 'brand':
        return item.brand.name if getattr(item, 'brand', None) else ''
    if target == 'stock_status':
        return 'LIVE' if sold else (getattr(item, 'latest_status', '') or 'LIVE')
    so_map = {
        'so_client_name': 'latest_client', 'so_invoice_no': 'latest_invoice',
        'so_olf_dc_number': 'latest_olf_dc', 'so_stock_status': 'latest_status',
        'so_stock_out_date': 'latest_out_date',
    }
    if target in so_map:
        return getattr(item, so_map[target], '') or ''
    value = getattr(item, target, '')
    return '' if value is None else value


def _write_category_sheet(ws, items, import_key, sold):
    from apps.core.importers import HEADER_MAPS

    header_map = HEADER_MAPS[f'{import_key}_stock_out' if sold else import_key]
    ws.append(list(header_map.keys()))
    _style_header(ws)
    targets = list(header_map.values())
    for item in items:
        _append_row(ws, [_import_cell(item, t, sold) for t in targets])


def _write_controller_sheet(ws, sold=False):
    from apps.categories.views import CONTROLLER_EXPORT_HEADERS, controller_export_rows
    from apps.core.importers import STOCK_OUT_APPEND_COLUMNS

    headers = list(CONTROLLER_EXPORT_HEADERS) + (list(STOCK_OUT_APPEND_COLUMNS) if sold else [])
    ws.append(headers)
    _style_header(ws)
    for values, product in controller_export_rows(sold):
        _append_row(ws, values + (_out_details(product) if sold else []))


def _write_server_sheet(ws, sold=False):
    from apps.servers.views import SERVER_EXPORT_HEADERS, _exclude_out_or_frozen, _in_stock_components, _server_queryset

    servers = _server_queryset().filter(latest_type='OUT') if sold else _exclude_out_or_frozen(_server_queryset())
    from apps.core.importers import STOCK_OUT_APPEND_COLUMNS

    ws.append(list(SERVER_EXPORT_HEADERS) + (list(STOCK_OUT_APPEND_COLUMNS) if sold else []))
    _style_header(ws)

    group = 0
    for server in servers:
        group += 1
        cabinet_serial = server.product.serial_no if server.product else ''
        _append_row(ws, [
            group,
            server.testing_date or '',
            server.tested_by or '',
            server.machine_type or '',
            server.machine_no or '',
            server.service_tag or '',
            server.model or '',
            'CABINET',
            server.part_no or '',
            server.alt_part_no or '',
            cabinet_serial,
            server.alt_serial_no or '',
            server.specs or '',
            server.barcode or '',
            server.qty or 1,
            server.status or '',
            server.location or '',
            server.reference_location or '',
            '',
            server.remark or '',
        ] + (_out_details(server.product) if sold else []))
        component_rows = server.components.select_related('product', 'product__category').all() if sold else _in_stock_components(server)
        for component in component_rows:
            if component.product_id == server.product_id or (getattr(component, 'spare_type', '') or '').upper() == 'CABINET':
                continue  # cabinet is already the first row of the group
            _append_row(ws, [
                group,
                server.testing_date or '',
                server.tested_by or '',
                server.machine_type or '',
                server.machine_no or '',
                server.service_tag or '',
                server.model or '',
                getattr(component, 'spare_type', '') or (component.product.category.name if component.product and component.product.category else ''),
                component.part_no or '',
                component.alt_part_no or '',
                component.serial_no or (component.product.serial_no if component.product else ''),
                component.alt_serial_no or '',
                component.specs or '',
                component.barcode or '',
                getattr(component, 'qty', 1) or 1,
                getattr(component, 'working_status', '') or '',
                component.location or server.location or '',
                component.reference_location or '',
                cabinet_serial,
                component.remark or '',
            ] + (_out_details(component.product) if sold else []))


def export_daily_inventory_snapshots(output_dir=None, export_date=None):
    from apps.categories.views import LIST_MODELS, _annotated_category_queryset
    from apps.core.importers import IMPORT_LABELS

    export_date = export_date or timezone.localdate()
    export_root = Path(output_dir or settings.MEDIA_ROOT) / 'exports' / export_date.isoformat()
    export_root.mkdir(parents=True, exist_ok=True)

    outputs = {}
    for state in ('live', 'stocked_out'):
        sold = state == 'stocked_out'
        workbook = Workbook()
        workbook.remove(workbook.active)
        for import_key, list_key in SIMPLE_EXPORT_KEYS.items():
            config = LIST_MODELS[list_key]
            qs = _annotated_category_queryset(config['model'], sold=sold)
            qs = qs.order_by('-latest_out_date', '-id') if sold else qs.order_by('id')
            ws = workbook.create_sheet(_safe_sheet_name(IMPORT_LABELS[import_key]))
            _write_category_sheet(ws, qs.iterator(chunk_size=1000), import_key, sold)
        _write_controller_sheet(workbook.create_sheet(IMPORT_LABELS['controller']), sold=sold)
        _write_server_sheet(workbook.create_sheet(IMPORT_LABELS['server']), sold=sold)

        file_name = f'inventory-{state}-{export_date.isoformat()}.xlsx'
        file_path = export_root / file_name
        workbook.save(file_path)
        outputs[state] = str(file_path)

    return outputs


def send_daily_inventory_email(recipients=None, output_dir=None, export_date=None):
    """Generate the daily snapshots and email them as Excel attachments.

    Recipients default to the active "Daily inventory report" rows of
    ReportRecipient (Admin Panel -> Report recipients), falling back to
    settings.DAILY_REPORT_RECIPIENTS. Returns a dict with the send result and
    the generated file paths.
    """
    from django.core.mail import EmailMessage
    from apps.core.notifications import get_recipients

    export_date = export_date or timezone.localdate()
    outputs = export_daily_inventory_snapshots(output_dir=output_dir, export_date=export_date)

    recipients = recipients or get_recipients('DAILY_REPORT')
    if not recipients:
        return {'sent': False, 'reason': 'no recipients configured', 'outputs': outputs}
    if settings.EMAIL_BACKEND.endswith('console.EmailBackend'):
        return {
            'sent': False, 'outputs': outputs,
            'reason': 'SMTP is not configured (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD missing in .env), '
                      'so nothing was actually delivered',
        }

    subject = f'Daily Inventory Report — {export_date.isoformat()}'
    body = (
        f'Attached are the automated inventory snapshots for {export_date.isoformat()}:\n\n'
        '  • inventory-live — everything currently in stock\n'
        '  • inventory-stocked_out — everything stocked out / sold\n\n'
        'Each workbook has one sheet per category (Spares, Card, CPU, Hard Disk, Memory, '
        'Networking Spare, Rail Kit, SFP, Controller, Server).\n\n'
        'To re-import: Import page -> choose the category -> upload the SAME file '
        '(the sheet with that category name is read). Use the normal import for the live '
        'file and the "<category> — Stock Out" import for the stocked-out file.\n\n'
        'This is an automated message from InvenTrack.'
    )
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        to=recipients,
    )
    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    for path in outputs.values():
        p = Path(path)
        email.attach(p.name, p.read_bytes(), content_type)

    email.send(fail_silently=False)
    return {'sent': True, 'recipients': recipients, 'outputs': outputs}
