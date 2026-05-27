from django.http import JsonResponse
from datetime import date, datetime

from django.shortcuts import render
from apps.inventory.models import InventoryTransaction
from apps.core.models import Product
from django.utils.timezone import now

# Create your views here.
 
def stock_out(request):
    if request.method == 'POST':
 
        product_id   = request.POST.get('product_id')
        client_name  = request.POST.get('client_name', '')
        invoice_no   = request.POST.get('invoice_no', '')
        stock_status = request.POST.get('stock_status', 'SALE')
        date_value   = request.POST.get('stock_out_date', '')
 
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found'})
 
        # carry store_location forward from last transaction
        last_txn = InventoryTransaction.objects.filter(
            product=product
        ).order_by('-created_at').first()
 
        store_location = (
            last_txn.store_location if last_txn else 'WH1'
        )
 
        try:
            stock_out_date = (
                datetime.strptime(date_value, '%Y-%m-%d').date()
                if date_value else date.today()
            )
        except ValueError:
            stock_out_date = date.today()
 
        InventoryTransaction.objects.create(
            product          = product,
            transaction_type = 'OUT',
            store_location   = store_location,
            stock_status     = stock_status,
            stock_out_date   = stock_out_date,
            client_name      = client_name,
            invoice_no       = invoice_no,
        )
 
        return JsonResponse({'success': True, 'status': stock_status})
 
    return JsonResponse({'success': False, 'error': 'Invalid method'})



def audit_spare(request):
    if request.method == 'POST':
 
        product_id   = request.POST.get('product_id')
        audit_remark = request.POST.get('audit_remark', '')
        audited_on   = request.POST.get('audited_on', '')
 
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found'})
 
        last_txn = InventoryTransaction.objects.filter(
            product=product
        ).order_by('-created_at').first()
 
        InventoryTransaction.objects.create(
            product          = product,
            transaction_type = 'AUDIT',
            store_location   = last_txn.store_location if last_txn else 'WH1',
            stock_status     = last_txn.stock_status   if last_txn else 'LIVE',
            audited_on       = audited_on or now().date(),
            audited_by       = request.user if request.user.is_authenticated else None,
            audit_remark     = audit_remark,
        )
 
        return JsonResponse({'success': True})
 
    return JsonResponse({'success': False, 'error': 'Invalid method'})


def audit_history(request, product_id):

    audits = InventoryTransaction.objects.filter(
        product_id=product_id,
        transaction_type='AUDIT'
    ).order_by('-created_at')

    data = []

    for a in audits:
        data.append({
            "date": a.audited_on,
            "user": a.audited_by.username if a.audited_by else "",
            "location": a.store_location,
            "status": a.stock_status,
            "remark": a.audit_remark
        })

    return JsonResponse({"data": data})


def audit_report(request):

    audits = InventoryTransaction.objects.filter(
        transaction_type='AUDIT'
    ).select_related('product', 'audited_by').order_by('-created_at')

    return render(request, 'spare/audit_report.html', {
        'audits': audits
    })
    
    

def check_product_membership(request):
    """
    Given a product_id, returns whether the product is part of
    a server or controller, with their labels.
    Used to show warning before stock-out / audit.
    """
    from apps.servers.models import ServerComponent
    from apps.categories.models import Spare
 
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({'in_server': False, 'in_controller': False})
 
    result = {'in_server': False, 'in_controller': False,
              'server_label': '', 'controller_label': ''}
 
    # check server
    sc = ServerComponent.objects.filter(
        product_id=product_id
    ).select_related('server').first()
 
    if sc:
        result['in_server']     = True
        result['server_label']  = (
            f"{sc.server.machine_no or ''} — "
            f"{sc.server.model or ''} "
            f"[{sc.server.service_tag}]"
        ).strip(' —')
 
    # check controller (via Spare.controller FK)
    try:
        spare = Spare.objects.select_related('controller__product').get(
            product_id=product_id
        )
        if spare.controller:
            result['in_controller']    = True
            result['controller_label'] = (
                f"{spare.controller.model or ''} "
                f"[{spare.controller.product.serial_no}]"
            )
    except Spare.DoesNotExist:
        pass
 
    return JsonResponse(result)