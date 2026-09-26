"""Shared, server-side filters for every inventory list (live, sold, faulty,
stock-status, servers ...).

One implementation so all lists behave identically:

    status     latest stock status            (?status=FAULTY)
    store      latest warehouse               (?store=WH2)
    brand      brand of the item              (?brand=<Brand id>)
    installed  yes / no — part of a server or controller  (?installed=yes)
    date_from  }  Out date on sold lists, otherwise the date the item was
    date_to    }  added                        (?date_from=2026-01-01)

Filters are applied to the whole queryset BEFORE pagination, so counts,
pages and exports-by-link all agree with what is on screen. A filter is only
offered / applied when the list actually supports it (it looks at the
queryset's annotations and model fields), and unknown or malformed values
are ignored instead of raising.
"""
from django.utils.dateparse import parse_date

FILTER_PARAMS = ('status', 'store', 'brand', 'installed', 'date_from', 'date_to')

# Statuses an item can carry while still IN stock vs. every status (sold lists).
IN_STOCK_STATUSES = ('LIVE', 'FAULTY', 'DAMAGED', 'TESTING', 'ON_APPROVAL', 'EMPTY', 'REFILL', 'SCRAP')


def _annotation(qs, *names):
    annotations = qs.query.annotations
    for name in names:
        if name in annotations:
            return name
    return None


def _model_field(qs, name):
    try:
        return qs.model._meta.get_field(name)
    except Exception:
        return None


def _clean(request, name):
    return (request.GET.get(name) or '').strip()


def apply_list_filters(request, qs, *, hide=(), status_options=None, sold=None):
    """Return (filtered_queryset, filter_context).

    hide            filter names not to offer/apply on this page (e.g. the
                    status-list page already fixes the status).
    status_options  override the choices shown in the Status dropdown.
    sold            True/False forces sold-list behaviour (Out date filter, all
                    statuses); default: detected from the queryset.
    """
    from apps.core.models import Brand
    from apps.inventory.models import InventoryTransaction

    hide = set(hide)
    status_field = None if 'status' in hide else _annotation(qs, 'latest_status')
    store_field = None if 'store' in hide else _annotation(qs, 'latest_location', 'latest_store')
    brand_field = _model_field(qs, 'brand') if 'brand' not in hide else None
    is_sold = (_annotation(qs, 'latest_out_date') is not None) if sold is None else sold
    if 'date' in hide:
        date_lookup = None
    elif is_sold and _annotation(qs, 'latest_out_date'):
        date_lookup = 'latest_out_date'
    elif _model_field(qs, 'created_at') is not None:
        date_lookup = 'created_at__date'
    else:
        date_lookup = None

    status = _clean(request, 'status').upper()
    store = _clean(request, 'store').upper()
    brand = _clean(request, 'brand')
    date_from = parse_date(_clean(request, 'date_from')) if date_lookup else None
    date_to = parse_date(_clean(request, 'date_to')) if date_lookup else None

    if status_options is None:
        all_choices = list(InventoryTransaction.STOCK_STATUS)
        status_options = all_choices if is_sold else [c for c in all_choices if c[0] in IN_STOCK_STATUSES]
    valid_statuses = {value for value, _ in status_options}
    valid_stores = {value for value, _ in InventoryTransaction.STORE_LOCATION}

    if status_field and status in valid_statuses:
        qs = qs.filter(**{status_field: status})
    else:
        status = ''
    if store_field and store in valid_stores:
        qs = qs.filter(**{store_field: store})
    else:
        store = ''

    brand_options = []
    if brand_field is not None:
        brand_options = [(str(b.pk), b.name) for b in Brand.objects.order_by('name')]
        if brand and brand in dict(brand_options):
            if getattr(brand_field, 'is_relation', False):
                qs = qs.filter(brand_id=brand)
            else:  # plain text column (e.g. Product.brand) — match by name
                qs = qs.filter(brand__iexact=dict(brand_options)[brand])
        else:
            brand = ''
    else:
        brand = ''

    installed = _clean(request, 'installed').lower()
    product_ref = None
    if 'installed' not in hide:
        if _model_field(qs, 'product') is not None and qs.model.__name__ != 'Server':
            product_ref = 'product_id'
        elif qs.model.__name__ == 'Product':
            product_ref = 'pk'
    if product_ref and installed in ('yes', 'no'):
        from django.db.models import Exists, OuterRef
        from apps.categories.models import Spare
        from apps.servers.models import ServerComponent
        is_installed = Exists(ServerComponent.objects.filter(product_id=OuterRef(product_ref))) |             Exists(Spare.objects.filter(product_id=OuterRef(product_ref), controller__isnull=False))
        qs = qs.annotate(_is_installed=is_installed).filter(_is_installed=(installed == 'yes'))
    else:
        installed = ''

    if date_lookup and date_from:
        qs = qs.filter(**{f'{date_lookup}__gte': date_from})
    if date_lookup and date_to:
        qs = qs.filter(**{f'{date_lookup}__lte': date_to})

    values = {
        'status': status, 'store': store, 'brand': brand, 'installed': installed,
        'date_from': date_from.isoformat() if date_from else '',
        'date_to': date_to.isoformat() if date_to else '',
    }
    return qs, {
        'values': values,
        'active_count': sum(1 for v in values.values() if v),
        'show_status': status_field is not None,
        'show_store': store_field is not None,
        'show_brand': brand_field is not None,
        'show_installed': product_ref is not None,
        'show_date': date_lookup is not None,
        'date_label': 'Out date' if is_sold else 'Added on',
        'status_options': list(status_options),
        'store_options': list(InventoryTransaction.STORE_LOCATION),
        'brand_options': brand_options,
    }
