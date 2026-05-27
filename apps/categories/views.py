from datetime import date
from urllib import request
from django.db.models import OuterRef, Subquery

from django.http import JsonResponse
from django.shortcuts import render, redirect
from apps.categories.models import CPU, Spare, Card
from apps.core.services import create_product_and_railkit, create_controller_with_components, create_product_and_card, create_product_and_cpu, create_product_and_memory, create_product_and_sfp, create_product_and_spare, create_product_and_harddisk
from apps.core.models import Product, SpareCategory, Brand
from django.db.models import OuterRef, Subquery, Value, CharField
from apps.servers.models import ServerComponent

from django.contrib import messages

from apps.inventory.models import InventoryTransaction

def add_spare(request):
    if request.method == "POST":

        try:
            data_map = {
                'category': request.POST.getlist('category[]'),
                'brand': request.POST.getlist('brand[]'),
                'model': request.POST.getlist('model[]'),
                'part_no': request.POST.getlist('part_no[]'),
                'alt_part_no': request.POST.getlist('alt_part_no[]'),
                'serial_no': request.POST.getlist('serial_no[]'),
                'alt_serial_no': request.POST.getlist('alt_serial_no[]'),
                'specs': request.POST.getlist('specs[]'),
                'qty': request.POST.getlist('qty[]'),
                'barcode': request.POST.getlist('barcode[]'),
                'location': request.POST.getlist('location[]'),
                'reference_location': request.POST.getlist('reference_location[]'),
                'remark': request.POST.getlist('remark[]'),
                'store_location': request.POST.getlist('store_location[]'),
                'stock_status': request.POST.getlist('stock_status[]'),
            }

            total = len(data_map['serial_no'])

            for i in range(total):
                if not data_map['serial_no'][i]:
                    continue

                row = {k: v[i] for k, v in data_map.items()}

                create_product_and_spare(row)

            messages.success(request, "Spare added successfully")

        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'spare/add_spare.html', {
        'categories': SpareCategory.objects.all(),
        'brands': Brand.objects.all()
    })

def check_serial(request):
    serial = request.GET.get('serial_no')

    exists = Product.objects.filter(serial_no=serial).exists()

    return JsonResponse({'exists': exists})



def spare_list(request):
    from apps.categories.models import Spare
    from apps.inventory.models import InventoryTransaction
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')
 
    spares = Spare.objects.select_related(
        'product', 'product__category',
        'controller', 'controller__product',
    ).annotate(
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date = Subquery(latest_audit.values('audited_on')[:1]),
        # server membership
        server_label    = Subquery(
            ServerComponent.objects.filter(
                product=OuterRef('product')
            ).values('server__machine_no')[:1]
        ),
        server_service_tag = Subquery(
            ServerComponent.objects.filter(
                product=OuterRef('product')
            ).values('server__service_tag')[:1]
        ),
        server_model_label = Subquery(
            ServerComponent.objects.filter(
                product=OuterRef('product')
            ).values('server__model')[:1]
        ),
        server_pk = Subquery(
            ServerComponent.objects.filter(
                product=OuterRef('product')
            ).values('server__id')[:1]
        ),
    ).exclude(latest_type='OUT')
 
    return render(request, 'spare/list.html', {'spares': spares})
 
 
# # NEW VIEW — components API used by controller list page
# def controller_components(request, controller_id):
#     from apps.categories.models import Controller
 
#     try:
#         ctrl = Controller.objects.get(id=controller_id)
#     except Controller.DoesNotExist:
#         return JsonResponse({'components': []})
 
#     latest_txn = InventoryTransaction.objects.filter(
#         product=OuterRef('product')
#     ).order_by('-created_at')
 
#     components = ctrl.components.select_related(
#         'product', 'product__category', 'brand'
#     ).annotate(
#         latest_location=Subquery(latest_txn.values('store_location')[:1]),
#         latest_status=Subquery(latest_txn.values('stock_status')[:1]),
#     )
 
#     data = []
#     for comp in components:
#         data.append({
#             'category':  comp.product.category.name,
#             'brand':     str(comp.brand) if comp.brand else '',
#             'model':     comp.model or '',
#             'part_no':   comp.part_no or '',
#             'serial_no': comp.product.serial_no,
#             'specs':     comp.specs or '',
#             'barcode':   comp.barcode or '',
#             'store':     comp.latest_location or '-',
#             'status':    comp.latest_status or '-',
#         })
 
#     return JsonResponse({'components': data})

# 🔥 INLINE UPDATE (AJAX)
def update_spare_field(request):
    if request.method == "POST":
        spare_id = request.POST.get('id')
        field = request.POST.get('field')
        value = request.POST.get('value')

        spare = Spare.objects.get(id=spare_id)

        setattr(spare, field, value)
        spare.save()

        return JsonResponse({'success': True})

    return JsonResponse({'success': False})


def spare_out_report(request):

    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')

    spares = Spare.objects.select_related('product').annotate(
        latest_type=Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location=Subquery(latest_txn.values('store_location')[:1]),
        latest_status=Subquery(latest_txn.values('stock_status')[:1]),
        latest_client=Subquery(latest_txn.values('client_name')[:1]),
        latest_invoice=Subquery(latest_txn.values('invoice_no')[:1]),
        latest_out_date=Subquery(latest_txn.values('stock_out_date')[:1]),
    ).filter(
        latest_type='OUT'   # 🔥 ONLY STOCKED OUT
    )

    return render(request, 'spare/spare_out_report.html', {
        'spares': spares
    })
    

def add_card(request):

    if request.method == "POST":

        data_map = {
            'brand': request.POST.getlist('brand[]'),
            'oem': request.POST.getlist('oem[]'),
            'brand_model_no': request.POST.getlist('brand_model_no[]'),
            'interface': request.POST.getlist('interface[]'),
            'part_no': request.POST.getlist('part_no[]'),
            'alt_part_no': request.POST.getlist('alt_part_no[]'),
            'serial_no': request.POST.getlist('brand_serial_no_1[]'),
            'brand_serial_no_1': request.POST.getlist('brand_serial_no_1[]'),
            'capacity': request.POST.getlist('capacity[]'),
            'port': request.POST.getlist('port[]'),
            'barcode': request.POST.getlist('barcode[]'),
            'location': request.POST.getlist('location[]'),
            'reference_location': request.POST.getlist('reference_location[]'),
            'remark': request.POST.getlist('remark[]'),
            'store_location': request.POST.getlist('store_location[]'),
            'stock_status': request.POST.getlist('stock_status[]'),
        }

        total = len(data_map['serial_no'])

        for i in range(total):
            if not data_map['serial_no'][i]:
                continue

            row = {k: v[i] for k, v in data_map.items()}

            create_product_and_card(row)

    return render(request, 'card/add_card.html', {'brands': Brand.objects.all()})



def card_list(request):

    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')

    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')

    cards = Card.objects.select_related('product').annotate(
        latest_type=Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location=Subquery(latest_txn.values('store_location')[:1]),
        latest_status=Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date=Subquery(latest_audit.values('audited_on')[:1]),
    ).exclude(
        latest_type='OUT'
    )

    return render(request, 'card/list.html', {
        'cards': cards
    })


def add_cpu(request):
    if request.method == "POST":
        try:
            data_map = {
                'brand': request.POST.getlist('brand[]'),
                'model': request.POST.getlist('model[]'),
                'part_no': request.POST.getlist('part_no[]'),
                'serial_no': request.POST.getlist('part_no[]'),
                'no_of_cores': request.POST.getlist('no_of_cores[]'),
                'no_of_threads': request.POST.getlist('no_of_threads[]'),
                'ghz': request.POST.getlist('ghz[]'),
                'frequency': request.POST.getlist('frequency[]'),
                'cache': request.POST.getlist('cache[]'),
                'barcode': request.POST.getlist('barcode[]'),
                'location': request.POST.getlist('location[]'),
                'reference_location': request.POST.getlist('reference_location[]'),
                'remark': request.POST.getlist('remark[]'),
                'store_location': request.POST.getlist('store_location[]'),
                'stock_status': request.POST.getlist('stock_status[]'),
            }

            total = len(data_map['serial_no'])

            for i in range(total):
                serial = data_map['serial_no'][i].strip()
                if not serial:
                    continue

                row = {}
                for key, value_list in data_map.items():
                    try:
                        row[key] = value_list[i]
                    except IndexError:
                        row[key] = None

                if not row.get('store_location'):
                    row['store_location'] = 'WH1'
                if not row.get('stock_status'):
                    row['stock_status'] = 'LIVE'

                create_product_and_cpu(row)

            messages.success(request, "PROCESSOR added successfully")
            return redirect('add_cpu')

        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'cpu/add_cpu.html', {
        'brands': Brand.objects.all()
    })


def cpu_list(request):
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')
 
    cpus = CPU.objects.select_related(
        'product', 'product__category', 'brand'
    ).annotate(
        latest_type=Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location=Subquery(latest_txn.values('store_location')[:1]),
        latest_status=Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date=Subquery(latest_audit.values('audited_on')[:1]),
    ).exclude(
        latest_type='OUT'
    )
 
    return render(request, 'cpu/cpu_list.html', {
        'cpus': cpus
    })
 
 
def update_cpu_field(request):
    """Inline edit handler for CPU fields: location, reference_location, remark"""
 
    ALLOWED_FIELDS = ['location', 'reference_location', 'remark']
 
    if request.method == 'POST':
        cpu_id = request.POST.get('id')
        field = request.POST.get('field')
        value = request.POST.get('value')
 
        if field not in ALLOWED_FIELDS:
            return JsonResponse({'success': False, 'error': 'Invalid field'})
 
        try:
            cpu = CPU.objects.get(id=cpu_id)
            setattr(cpu, field, value)
            cpu.save()
            return JsonResponse({'success': True})
        except CPU.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'CPU not found'})
 
    return JsonResponse({'success': False})



def add_controller(request):
    if request.method == 'POST':
        try:
            # --- CABINET DATA ---
            cabinet_data = {
                'brand':                request.POST.get('cabinet_brand', ''),
                'model':                request.POST.get('cabinet_model', ''),
                'part_no':              request.POST.get('cabinet_part_no', ''),
                'alt_part_no':          request.POST.get('cabinet_alt_part_no', ''),
                'serial_no':            request.POST.get('cabinet_serial_no', ''),
                'alt_serial_no':        request.POST.get('cabinet_alt_serial_no', ''),
                'specs':                request.POST.get('cabinet_specs', ''),
                'qty':                  request.POST.get('cabinet_qty', 1),
                'barcode':              request.POST.get('cabinet_barcode', ''),
                'location':             request.POST.get('cabinet_location', ''),
                'reference_location':   request.POST.get('cabinet_reference_location', ''),
                'parent_child_location':request.POST.get('cabinet_parent_child_location', ''),
                'remark':               request.POST.get('cabinet_remark', ''),
                'store_location':       request.POST.get('cabinet_store_location', 'WH1'),
                'stock_status':         request.POST.get('cabinet_stock_status', 'LIVE'),
            }
 
            # --- COMPONENTS (multi-row) ---
            fields = [
                'product_category', 'brand', 'model', 'part_no',
                'alt_part_no', 'serial_no', 'alt_serial_no',
                'specs', 'qty', 'barcode', 'remark',
            ]
 
            lists = {f: request.POST.getlist(f'comp_{f}[]') for f in fields}
            total = len(lists['serial_no'])
 
            components = []
            for i in range(total):
                row = {}
                for f in fields:
                    try:
                        row[f] = lists[f][i]
                    except IndexError:
                        row[f] = ''
                components.append(row)
 
            create_controller_with_components(cabinet_data, components)
 
            messages.success(request, 'Controller created successfully.')
            return redirect('add_controller')
 
        except Exception as e:
            messages.error(request, str(e))
 
    return render(request, 'controller/add_controller.html', {
        'brands': Brand.objects.all(),
        'spare_categories': SpareCategory.objects.all(),
    })
 
 
def controller_list(request):
    from apps.categories.models import Controller
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')
 
    controllers = Controller.objects.select_related(
        'product', 'product__category', 'brand'
    ).annotate(
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date = Subquery(latest_audit.values('audited_on')[:1]),
    ).exclude(latest_type='OUT')
 
    return render(request, 'controller/controller_list.html', {
        'controllers':      controllers,
        'spare_categories': SpareCategory.objects.all(),   # for add-component modal
        'brands':           Brand.objects.all(),           # for add-component modal
    })
 
 
def update_controller_field(request):
    from apps.categories.models import Controller
 
    ALLOWED_FIELDS = ['location', 'reference_location', 'parent_child_location', 'remark']
 
    if request.method == 'POST':
        ctrl_id = request.POST.get('id')
        field   = request.POST.get('field')
        value   = request.POST.get('value')
 
        if field not in ALLOWED_FIELDS:
            return JsonResponse({'success': False, 'error': 'Invalid field'})
 
        try:
            ctrl = Controller.objects.get(id=ctrl_id)
            setattr(ctrl, field, value)
            ctrl.save()
            return JsonResponse({'success': True})
        except Controller.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'})
 
    return JsonResponse({'success': False})


def add_controller_component(request):
    """
    AJAX endpoint — adds one or more spare components to an
    existing Controller. Called from the controller list modal.
    """
    from apps.categories.models import Controller, Spare
 
    if request.method == 'POST':
        try:
            controller_id = request.POST.get('controller_id')
            controller    = Controller.objects.select_related(
                'product'
            ).get(id=controller_id)
 
            fields = [
                'product_category', 'brand', 'model', 'part_no',
                'alt_part_no', 'serial_no', 'alt_serial_no',
                'specs', 'qty', 'barcode', 'remark',
            ]
 
            lists = {f: request.POST.getlist(f'comp_{f}[]') for f in fields}
            total = len(lists['serial_no'])
 
            added = 0
 
            for i in range(total):
                serial = lists['serial_no'][i].strip().upper()
                if not serial:
                    continue
 
                # duplicate check
                if Product.objects.filter(serial_no=serial).exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'Serial already exists: {serial}'
                    })
 
                row = {}
                for f in fields:
                    try:
                        row[f] = lists[f][i]
                    except IndexError:
                        row[f] = ''
 
                comp_category_name = row.get('product_category', '').strip().upper()
                comp_category, _   = SpareCategory.objects.get_or_create(
                    name=comp_category_name
                )
 
                comp_brand_name = row.get('brand', '').strip().upper()
                comp_brand = None
                if comp_brand_name:
                    comp_brand, _ = Brand.objects.get_or_create(name=comp_brand_name)
 
                comp_name = (
                    f'CONTROLLER - '
                    f"{comp_category_name} - "
                    f"{row.get('model', '')} - "
                    f"{comp_brand_name}"
                ).strip(' -')
 
                comp_product = Product.objects.create(
                    category  = comp_category,
                    serial_no = serial,
                    part_no   = row.get('part_no'),
                    brand     = comp_brand,
                    model     = row.get('model'),
                    name      = comp_name
                )
 
                Spare.objects.create(
                    product            = comp_product,
                    controller         = controller,
                    brand              = comp_brand,
                    model              = row.get('model'),
                    part_no            = row.get('part_no'),
                    alt_part_no        = row.get('alt_part_no'),
                    alt_serial_no      = row.get('alt_serial_no'),
                    specs              = row.get('specs'),
                    qty                = row.get('qty') or 1,
                    barcode            = row.get('barcode'),
                    # inherit controller location
                    location           = controller.location,
                    reference_location = controller.reference_location,
                    remark             = row.get('remark'),
                )
 
                # auto stock IN — inherit controller's last transaction location/status
                last_ctrl_txn = InventoryTransaction.objects.filter(
                    product=controller.product
                ).order_by('-created_at').first()
 
                InventoryTransaction.objects.create(
                    product          = comp_product,
                    transaction_type = 'IN',
                    store_location   = last_ctrl_txn.store_location if last_ctrl_txn else 'WH1',
                    stock_status     = last_ctrl_txn.stock_status   if last_ctrl_txn else 'LIVE',
                    stock_in_date    = date.today()
                )
 
                added += 1
 
            return JsonResponse({'success': True, 'added': added})
 
        except Controller.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Controller not found'})
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': str(e),
                'trace': traceback.format_exc()
            })
 
    return JsonResponse({'success': False})
 
 
def controller_components(request, controller_id):
    """
    Returns all components for a controller with their latest
    transaction status — OUT items are flagged.
    """
    from apps.categories.models import Controller
 
    try:
        ctrl = Controller.objects.get(id=controller_id)
    except Controller.DoesNotExist:
        return JsonResponse({'components': []})
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    components = ctrl.components.select_related(
        'product', 'product__category', 'brand'
    ).annotate(
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_client   = Subquery(latest_txn.values('client_name')[:1]),
        latest_invoice  = Subquery(latest_txn.values('invoice_no')[:1]),
        latest_out_date = Subquery(latest_txn.values('stock_out_date')[:1]),
    )
 
    data = []
    for comp in components:
        is_out = (comp.latest_type == 'OUT')
        data.append({
            'id':          comp.id,
            'product_id':  comp.product.id,
            'category':    comp.product.category.name,
            'brand':       str(comp.brand) if comp.brand else '',
            'model':       comp.model    or '',
            'part_no':     comp.part_no  or '',
            'serial_no':   comp.product.serial_no,
            'specs':       comp.specs    or '',
            'barcode':     comp.barcode  or '',
            'store':       comp.latest_location or '-',
            'status':      comp.latest_status   or '-',
            'is_out':      is_out,
            'client':      comp.latest_client   or '',
            'invoice':     comp.latest_invoice  or '',
            'out_date':    str(comp.latest_out_date) if comp.latest_out_date else '',
        })
 
    return JsonResponse({'components': data})


def add_memory(request):
    if request.method == 'POST':
        try:
            data_map = {
                'brand':              request.POST.getlist('brand[]'),
                'oem':                request.POST.getlist('oem[]'),
                'model':              request.POST.getlist('model[]'),
                'part_no_1':          request.POST.getlist('part_no_1[]'),
                'part_no_2':          request.POST.getlist('part_no_2[]'),
                'part_no_3':          request.POST.getlist('part_no_3[]'),
                'size':               request.POST.getlist('size[]'),
                'ram_type':           request.POST.getlist('ram_type[]'),
                'ddr_version':        request.POST.getlist('ddr_version[]'),
                'frequency':          request.POST.getlist('frequency[]'),
                'rank':               request.POST.getlist('rank[]'),
                'serial_no':          request.POST.getlist('serial_no[]'),
                'qty':                request.POST.getlist('qty[]'),
                'barcode':            request.POST.getlist('barcode[]'),
                'location':           request.POST.getlist('location[]'),
                'reference_location': request.POST.getlist('reference_location[]'),
                'remark':             request.POST.getlist('remark[]'),
                'store_location':     request.POST.getlist('store_location[]'),
                'stock_status':       request.POST.getlist('stock_status[]'),
            }
 
            total = len(data_map['serial_no'])
 
            for i in range(total):
                serial = data_map['serial_no'][i].strip()
                if not serial:
                    continue
 
                row = {}
                for key, value_list in data_map.items():
                    try:
                        row[key] = value_list[i]
                    except IndexError:
                        row[key] = None
 
                if not row.get('store_location'):
                    row['store_location'] = 'WH1'
                if not row.get('stock_status'):
                    row['stock_status'] = 'LIVE'
 
                create_product_and_memory(row)
 
            messages.success(request, 'Memory added successfully.')
            return redirect('add_memory')
 
        except Exception as e:
            messages.error(request, str(e))
 
    return render(request, 'memory/add_memory.html', {
        'brands': Brand.objects.all(),
    })
 
 
def memory_list(request):
    from apps.categories.models import Memory
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')
 
    memories = Memory.objects.select_related(
        'product', 'product__category', 'brand'
    ).annotate(
        latest_type      = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location  = Subquery(latest_txn.values('store_location')[:1]),
        latest_status    = Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date  = Subquery(latest_audit.values('audited_on')[:1]),
    ).exclude(latest_type='OUT')
 
    return render(request, 'memory/memory_list.html', {'memories': memories})
 
 
def update_memory_field(request):
    from apps.categories.models import Memory
 
    ALLOWED_FIELDS = ['location', 'reference_location', 'remark']
 
    if request.method == 'POST':
        mem_id = request.POST.get('id')
        field  = request.POST.get('field')
        value  = request.POST.get('value')
 
        if field not in ALLOWED_FIELDS:
            return JsonResponse({'success': False, 'error': 'Invalid field'})
 
        try:
            mem = Memory.objects.get(id=mem_id)
            setattr(mem, field, value)
            mem.save()
            return JsonResponse({'success': True})
        except Memory.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'})
 
    return JsonResponse({'success': False})



def add_sfp(request):
    if request.method == 'POST':
        try:
            data_map = {
                'brand':              request.POST.getlist('brand[]'),
                'model':              request.POST.getlist('model[]'),
                'part_no':            request.POST.getlist('part_no[]'),
                'description':        request.POST.getlist('description[]'),
                'fibre_type':         request.POST.getlist('fibre_type[]'),
                'data_rate':          request.POST.getlist('data_rate[]'),
                'serial_no':          request.POST.getlist('serial_no[]'),
                'barcode':            request.POST.getlist('barcode[]'),
                'location':           request.POST.getlist('location[]'),
                'reference_location': request.POST.getlist('reference_location[]'),
                'remark':             request.POST.getlist('remark[]'),
                'store_location':     request.POST.getlist('store_location[]'),
                'stock_status':       request.POST.getlist('stock_status[]'),
            }
 
            total = len(data_map['serial_no'])
 
            for i in range(total):
                serial = data_map['serial_no'][i].strip()
                if not serial:
                    continue
 
                row = {}
                for key, value_list in data_map.items():
                    try:
                        row[key] = value_list[i]
                    except IndexError:
                        row[key] = None
 
                if not row.get('store_location'):
                    row['store_location'] = 'WH1'
                if not row.get('stock_status'):
                    row['stock_status'] = 'LIVE'
 
                create_product_and_sfp(row)
 
            messages.success(request, 'SFP added successfully.')
            return redirect('add_sfp')
 
        except Exception as e:
            messages.error(request, str(e))
 
    return render(request, 'sfp/add_sfp.html', {
        'brands': Brand.objects.all(),
    })
 
 
def sfp_list(request):
    from apps.categories.models import SFP
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')
 
    sfps = SFP.objects.select_related(
        'product', 'product__category', 'brand'
    ).annotate(
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date = Subquery(latest_audit.values('audited_on')[:1]),
    ).exclude(latest_type='OUT')
 
    return render(request, 'sfp/sfp_list.html', {'sfps': sfps})
 
 
def update_sfp_field(request):
    from apps.categories.models import SFP
 
    ALLOWED_FIELDS = ['location', 'reference_location', 'remark']
 
    if request.method == 'POST':
        sfp_id = request.POST.get('id')
        field  = request.POST.get('field')
        value  = request.POST.get('value')
 
        if field not in ALLOWED_FIELDS:
            return JsonResponse({'success': False, 'error': 'Invalid field'})
 
        try:
            sfp = SFP.objects.get(id=sfp_id)
            setattr(sfp, field, value)
            sfp.save()
            return JsonResponse({'success': True})
        except SFP.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'})
 
    return JsonResponse({'success': False})



def add_railkit(request):
    if request.method == 'POST':
        try:
            data_map = {
                'brand':              request.POST.getlist('brand[]'),
                'side':               request.POST.getlist('side[]'),
                'part_no':            request.POST.getlist('part_no[]'),
                'serial_no':          request.POST.getlist('serial_no[]'),
                'specs':              request.POST.getlist('specs[]'),
                'barcode':            request.POST.getlist('barcode[]'),
                'supported_model':    request.POST.getlist('supported_model[]'),
                'qty':                request.POST.getlist('qty[]'),
                'location':           request.POST.getlist('location[]'),
                'reference_location': request.POST.getlist('reference_location[]'),
                'remark':             request.POST.getlist('remark[]'),
                'store_location':     request.POST.getlist('store_location[]'),
                'stock_status':       request.POST.getlist('stock_status[]'),
            }
 
            total = len(data_map['serial_no'])
 
            for i in range(total):
                serial = data_map['serial_no'][i].strip()
                if not serial:
                    continue
 
                row = {}
                for key, value_list in data_map.items():
                    try:
                        row[key] = value_list[i]
                    except IndexError:
                        row[key] = None
 
                if not row.get('store_location'):
                    row['store_location'] = 'WH1'
                if not row.get('stock_status'):
                    row['stock_status'] = 'LIVE'
 
                create_product_and_railkit(row)
 
            messages.success(request, 'Rail Kit added successfully.')
            return redirect('add_railkit')
 
        except Exception as e:
            messages.error(request, str(e))
 
    return render(request, 'railkit/add_railkit.html', {
        'brands': Brand.objects.all(),
    })
 
 
def railkit_list(request):
    from apps.categories.models import RailKit
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')
 
    railkits = RailKit.objects.select_related(
        'product', 'product__category', 'brand'
    ).annotate(
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date = Subquery(latest_audit.values('audited_on')[:1]),
    ).exclude(latest_type='OUT')
 
    return render(request, 'railkit/railkit_list.html', {'railkits': railkits})
 
 
def update_railkit_field(request):
    from apps.categories.models import RailKit
 
    ALLOWED_FIELDS = ['location', 'reference_location', 'remark']
 
    if request.method == 'POST':
        rk_id = request.POST.get('id')
        field = request.POST.get('field')
        value = request.POST.get('value')
 
        if field not in ALLOWED_FIELDS:
            return JsonResponse({'success': False, 'error': 'Invalid field'})
 
        try:
            rk = RailKit.objects.get(id=rk_id)
            setattr(rk, field, value)
            rk.save()
            return JsonResponse({'success': True})
        except RailKit.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'})
 
    return JsonResponse({'success': False})


def add_harddisk(request):
    if request.method == 'POST':
        try:
            data_map = {
                'brand':              request.POST.getlist('brand[]'),
                'oem':                request.POST.getlist('oem[]'),
                'brand_model_no':     request.POST.getlist('brand_model_no[]'),
                'oem_model_no':       request.POST.getlist('oem_model_no[]'),
                'capacity':           request.POST.getlist('capacity[]'),
                'rpm':                request.POST.getlist('rpm[]'),
                'interface':          request.POST.getlist('interface[]'),
                'part_no':            request.POST.getlist('part_no[]'),
                'alt_part_no':        request.POST.getlist('alt_part_no[]'),
                'alt_fru_1':          request.POST.getlist('alt_fru_1[]'),
                'alt_fru_2':          request.POST.getlist('alt_fru_2[]'),
                'alt_fru_3':          request.POST.getlist('alt_fru_3[]'),
                'retail_part_no':     request.POST.getlist('retail_part_no[]'),
                'spare_part_tray':    request.POST.getlist('spare_part_tray[]'),
                'gpn_code':           request.POST.getlist('gpn_code[]'),
                'brand_serial_no':    request.POST.getlist('brand_serial_no[]'),
                'oem_serial_no':      request.POST.getlist('oem_serial_no[]'),
                'serial_no':          request.POST.getlist('serial_no[]'),
                'firmware':           request.POST.getlist('firmware[]'),
                'size':               request.POST.getlist('size[]'),
                'health':             request.POST.getlist('health[]'),
                'gb_s':               request.POST.getlist('gb_s[]'),
                'barcode':            request.POST.getlist('barcode[]'),
                'tray_barcode':       request.POST.getlist('tray_barcode[]'),
                'location':           request.POST.getlist('location[]'),
                'reference_location': request.POST.getlist('reference_location[]'),
                'remark':             request.POST.getlist('remark[]'),
                'store_location':     request.POST.getlist('store_location[]'),
                'stock_status':       request.POST.getlist('stock_status[]'),
            }
 
            total = len(data_map['serial_no'])
 
            for i in range(total):
                serial = data_map['serial_no'][i].strip()
                if not serial:
                    continue
 
                row = {}
                for key, value_list in data_map.items():
                    try:
                        row[key] = value_list[i]
                    except IndexError:
                        row[key] = None
 
                if not row.get('store_location'):
                    row['store_location'] = 'WH1'
                if not row.get('stock_status'):
                    row['stock_status'] = 'LIVE'
 
                create_product_and_harddisk(row)
 
            messages.success(request, 'Hard Disk added successfully.')
            return redirect('add_harddisk')
 
        except Exception as e:
            messages.error(request, str(e))
 
    return render(request, 'harddisk/add_harddisk.html', {
        'brands': Brand.objects.all(),
    })
 
 
def harddisk_list(request):
    from apps.categories.models import HardDisk
 
    latest_txn = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
 
    latest_audit = InventoryTransaction.objects.filter(
        product=OuterRef('product'),
        transaction_type='AUDIT'
    ).order_by('-created_at')
 
    harddisks = HardDisk.objects.select_related(
        'product', 'product__category', 'brand'
    ).annotate(
        latest_type     = Subquery(latest_txn.values('transaction_type')[:1]),
        latest_location = Subquery(latest_txn.values('store_location')[:1]),
        latest_status   = Subquery(latest_txn.values('stock_status')[:1]),
        last_audit_date = Subquery(latest_audit.values('audited_on')[:1]),
    ).exclude(latest_type='OUT')
 
    return render(request, 'harddisk/harddisk_list.html', {'harddisks': harddisks})
 
 
def update_harddisk_field(request):
    from apps.categories.models import HardDisk
 
    ALLOWED_FIELDS = ['location', 'reference_location', 'remark']
 
    if request.method == 'POST':
        hd_id = request.POST.get('id')
        field = request.POST.get('field')
        value = request.POST.get('value')
 
        if field not in ALLOWED_FIELDS:
            return JsonResponse({'success': False, 'error': 'Invalid field'})
 
        try:
            hd = HardDisk.objects.get(id=hd_id)
            setattr(hd, field, value)
            hd.save()
            return JsonResponse({'success': True})
        except HardDisk.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Not found'})
 
    return JsonResponse({'success': False})


def check_barcode(request):
    """
    AJAX endpoint — checks barcode uniqueness across ALL
    category tables in a single efficient query.
    """
    from apps.categories.models import (
        Spare, Card, CPU, Memory, SFP, RailKit, HardDisk, Controller
    )
 
    barcode = request.GET.get('barcode', '').strip().upper()
 
    if not barcode:
        return JsonResponse({'exists': False})
 
    exists = (
        Spare.objects.filter(barcode=barcode).exists()       or
        Card.objects.filter(barcode=barcode).exists()        or
        CPU.objects.filter(barcode=barcode).exists()         or
        Memory.objects.filter(barcode=barcode).exists()      or
        SFP.objects.filter(barcode=barcode).exists()         or
        RailKit.objects.filter(barcode=barcode).exists()     or
        HardDisk.objects.filter(barcode=barcode).exists()    or
        HardDisk.objects.filter(tray_barcode=barcode).exists() or
        Controller.objects.filter(barcode=barcode).exists()
    )
 
    return JsonResponse({'exists': exists})



def _annotate_membership(queryset, product_field='product'):
    """
    Annotates any category queryset with:
      - server_id, server_label  (if product is in a server)
      - controller_id, controller_label (if product is in a controller)
 
    product_field: the field path to the Product FK on the queryset model
    """
    from apps.servers.models import ServerComponent
    from apps.categories.models import Controller
 
    # Server membership
    server_comp = ServerComponent.objects.filter(
        product=OuterRef(product_field)
    ).select_related('server').order_by('-attached_at')
 
    # Controller membership (via Spare.controller)
    # For spare: OuterRef('id') → spare.controller_id
    # For other models: product → spare → controller (handled differently)
 
    queryset = queryset.annotate(
        server_label=Subquery(
            ServerComponent.objects.filter(
                product=OuterRef(product_field)
            ).values('server__machine_no')[:1]
        ),
        server_model_label=Subquery(
            ServerComponent.objects.filter(
                product=OuterRef(product_field)
            ).values('server__model')[:1]
        ),
        server_service_tag=Subquery(
            ServerComponent.objects.filter(
                product=OuterRef(product_field)
            ).values('server__service_tag')[:1]
        ),
        server_pk=Subquery(
            ServerComponent.objects.filter(
                product=OuterRef(product_field)
            ).values('server__id')[:1]
        ),
    )
 
    return queryset


from django.db.models import OuterRef, Subquery
from django.shortcuts import render

from apps.inventory.models import InventoryTransaction
from apps.servers.models import ServerComponent

from apps.categories.models import (
    Card,
    CPU,
    Memory,
    SFP,
    RailKit,
    HardDisk,
)


def _list_view_annotated(model_class, template, context_key):
    """
    Generic annotated list view for spare categories.
    """

    def view(request):

        latest_txn = InventoryTransaction.objects.filter(
            product_id=OuterRef('product_id')
        ).order_by('-created_at')

        latest_audit = InventoryTransaction.objects.filter(
            product_id=OuterRef('product_id'),
            transaction_type='AUDIT'
        ).order_by('-created_at')

        # IMPORTANT:
        # use product_id instead of product
        server_component = ServerComponent.objects.filter(
            product_id=OuterRef('product_id')
        )

        qs = (
            model_class.objects
            .select_related(
                'product',
                'product__category',
                'brand'
            )
            .annotate(

                # inventory
                latest_type=Subquery(
                    latest_txn.values('transaction_type')[:1]
                ),

                latest_location=Subquery(
                    latest_txn.values('store_location')[:1]
                ),

                latest_status=Subquery(
                    latest_txn.values('stock_status')[:1]
                ),

                last_audit_date=Subquery(
                    latest_audit.values('audited_on')[:1]
                ),

                # server membership
                server_label=Subquery(
                    server_component.values('server__machine_no')[:1]
                ),

                server_service_tag=Subquery(
                    server_component.values('server__service_tag')[:1]
                ),

                server_model_label=Subquery(
                    server_component.values('server__model')[:1]
                ),

                server_pk=Subquery(
                    server_component.values('server__id')[:1]
                ),
            )
            .exclude(latest_type='OUT')
        )

        # DEBUG
        for obj in qs[:5]:
            print(
                "PRODUCT:", obj.product_id,
                "SERVER:", obj.server_label,
                "TAG:", obj.server_service_tag,
            )

        return render(
            request,
            template,
            {
                context_key: qs
            }
        )

    return view


# views
card_list = _list_view_annotated(
    Card,
    'card/list.html',
    'cards'
)

cpu_list = _list_view_annotated(
    CPU,
    'cpu/cpu_list.html',
    'cpus'
)

memory_list = _list_view_annotated(
    Memory,
    'memory/memory_list.html',
    'memories'
)

sfp_list = _list_view_annotated(
    SFP,
    'sfp/sfp_list.html',
    'sfps'
)

railkit_list = _list_view_annotated(
    RailKit,
    'railkit/railkit_list.html',
    'railkits'
)

harddisk_list = _list_view_annotated(
    HardDisk,
    'harddisk/harddisk_list.html',
    'harddisks'
)