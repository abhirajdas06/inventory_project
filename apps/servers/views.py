import json
import traceback
from datetime import date
 
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.db.models import OuterRef, Subquery
 
from apps.core.models import Product, SpareCategory, Brand
from apps.core.services import create_server_with_components, add_server_component
from apps.inventory.models import InventoryTransaction
from apps.servers.models import Server, ServerComponent
 
 
# ── Create ────────────────────────────────────────────────
def add_server(request):
    if request.method == 'POST':
        try:
            server_data = {
                # server identity
                'machine_type':           request.POST.get('machine_type', ''),
                'machine_no':             request.POST.get('machine_no', ''),
                'service_tag':            request.POST.get('service_tag', ''),
                'model':                  request.POST.get('model', ''),
                'brand':                  request.POST.get('brand', ''),
                # cabinet fields  ← NEW
                'part_no':                request.POST.get('part_no', ''),
                'alt_part_no':            request.POST.get('alt_part_no', ''),
                'alt_serial_no':          request.POST.get('alt_serial_no', ''),
                'specs':                  request.POST.get('specs', ''),
                'qty':                    request.POST.get('qty', 1),
                'barcode':                request.POST.get('barcode', ''),
                # testing
                'testing_date':           request.POST.get('testing_date', ''),
                'tested_by':              request.POST.get('tested_by', ''),
                # status / location
                'status':                 request.POST.get('status', 'WORKING'),
                'location':               request.POST.get('location', ''),
                'reference_location':     request.POST.get('reference_location', ''),
                'parent_child_location':  request.POST.get('parent_child_location', ''),
                'remark':                 request.POST.get('remark', ''),
                'store_location':         request.POST.get('store_location', 'WH1'),
                'stock_status':           request.POST.get('stock_status', 'LIVE'),
            }
 
            comp_fields = [
                'spare_type', 'brand', 'model',
                'part_no', 'alt_part_no',
                'serial_no', 'alt_serial_no',
                'specs', 'barcode', 'qty',
                'working_status', 'location',
                'reference_location', 'parent_child_location', 'remark',
            ]
 
            lists      = {f: request.POST.getlist(f'comp_{f}[]') for f in comp_fields}
            total      = len(lists['serial_no'])
            components = []
 
            for i in range(total):
                row = {}
                for f in comp_fields:
                    try:
                        row[f] = lists[f][i]
                    except IndexError:
                        row[f] = ''
                components.append(row)
 
            create_server_with_components(server_data, components)
            messages.success(request, 'Server created successfully.')
            return redirect('server_list')
 
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, str(e))
 
    return render(request, 'servers/add_server.html', {
        'brands':           Brand.objects.all(),
        'spare_categories': SpareCategory.objects.all(),
    })
 
 
def _server_queryset():
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')

    return Server.objects.select_related(
        'product', 'brand'
    ).annotate(
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        latest_client   = Subquery(latest_txn.values('client_name')[:1]),
        latest_invoice  = Subquery(latest_txn.values('invoice_no')[:1]),
        latest_out_date = Subquery(latest_txn.values('stock_out_date')[:1]),
    ).order_by('-created_at')


# ── List ──────────────────────────────────────────────────
def server_list(request):
    servers = _server_queryset().exclude(latest_type='OUT')
 
    return render(request, 'servers/server_list.html', {
        'servers':          servers,
        'spare_categories': SpareCategory.objects.all(),   # ← this
        'brands':           Brand.objects.all(),
    })


def server_out_list(request):
    servers = _server_queryset().filter(latest_type='OUT')

    return render(request, 'servers/server_out_list.html', {
        'servers': servers,
    })
 
 
# ── Components API ────────────────────────────────────────
def server_components(request, server_id):
    """Returns all components with latest transaction info."""
    try:
        server = Server.objects.get(id=server_id)
    except Server.DoesNotExist:
        return JsonResponse({'components': []})
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    comps = server.components.select_related(
        'product', 'product__category'
    ).annotate(
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_client   = Subquery(latest_txn.values('client_name')[:1]),
        latest_invoice  = Subquery(latest_txn.values('invoice_no')[:1]),
        latest_out_date = Subquery(latest_txn.values('stock_out_date')[:1]),
    ).order_by('spare_type')
 
    data = []
    for c in comps:
        is_out = (c.latest_type == 'OUT')
        data.append({
            'id':          c.id,
            'product_id':  c.product.id,
            'spare_type':  c.spare_type or '',
            'part_no':     c.part_no    or '',
            'alt_part_no': c.alt_part_no or '',
            'serial_no':   c.serial_no  or c.product.serial_no,
            'alt_serial_no': c.alt_serial_no or '',
            'specs':       c.specs      or '',
            'barcode':     c.barcode    or '',
            'qty':         c.qty,
            'working_status': c.working_status or '',
            'location':    c.location   or '',
            'remark':      c.remark     or '',
            'store':       c.latest_location or '-',
            'status':      c.latest_status   or '-',
            'is_out':      is_out,
            'client':      c.latest_client   or '',
            'invoice':     c.latest_invoice  or '',
            'out_date':    str(c.latest_out_date) if c.latest_out_date else '',
        })
 
    return JsonResponse({'components': data, 'server_model': server.model})
 
 
# ── Add component to existing server ─────────────────────
def add_server_component_view(request):
    if request.method == 'POST':
        try:
            server_id = request.POST.get('server_id')
            server    = Server.objects.get(id=server_id)
 
            comp_fields = [
                'spare_type', 'brand', 'model',
                'part_no', 'alt_part_no',
                'serial_no', 'alt_serial_no',
                'specs', 'barcode', 'qty',
                'working_status', 'location',
                'reference_location', 'parent_child_location', 'remark',
            ]
 
            lists = {f: request.POST.getlist(f'comp_{f}[]') for f in comp_fields}
            total = len(lists['serial_no'])
            added = 0
 
            last_txn = InventoryTransaction.objects.filter(
                product=server.product
            ).order_by('-created_at').first()
 
            store_location = last_txn.store_location if last_txn else 'WH1'
            stock_status   = last_txn.stock_status   if last_txn else 'LIVE'
 
            for i in range(total):
                barcode = lists['barcode'][i].strip().upper() if i < len(lists['barcode']) else ''
                serial  = lists['serial_no'][i].strip().upper() if i < len(lists['serial_no']) else ''
 
                if not barcode and not serial:
                    continue
 
                # duplicate barcode check
                if barcode:
                    from apps.categories.models import Spare
                    if Spare.objects.filter(barcode=barcode).exists():
                        return JsonResponse({'success': False, 'error': f'Barcode already exists: {barcode}'})
 
                row = {}
                for f in comp_fields:
                    try:
                        row[f] = lists[f][i]
                    except IndexError:
                        row[f] = ''
 
                add_server_component(server, row, store_location, stock_status)
                added += 1
 
            return JsonResponse({'success': True, 'added': added})
 
        except Server.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Server not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e), 'trace': traceback.format_exc()})
 
    return JsonResponse({'success': False})
 
 
# ── Inline edit ───────────────────────────────────────────
def update_server_field(request):
    ALLOWED = ['location', 'reference_location', 'parent_child_location', 'remark', 'status']
 
    if request.method == 'POST':
        srv_id = request.POST.get('id')
        field  = request.POST.get('field')
        value  = request.POST.get('value')
 
        if field not in ALLOWED:
            return JsonResponse({'success': False, 'error': 'Invalid field'})
 
        try:
            srv = Server.objects.get(id=srv_id)
            setattr(srv, field, value)
            srv.save()
            return JsonResponse({'success': True})
        except Server.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'})
 
    return JsonResponse({'success': False})
 
