"""Dashboard card numbers — one place both the dashboard page and the
per-card detail modal (AJAX) pull from, so the two always agree.

Every model here has a `.product` FK/OneToOne to Product, which is how its
current stock state (in/out, status, warehouse) is read: the same
InventoryTransaction-subquery pattern used throughout the app.
"""
from collections import OrderedDict

from django.db.models import Count, OuterRef, Q, Subquery

FAULTY_DAMAGED = ('FAULTY', 'DAMAGED')
FAULTY_DAMAGED_SCRAP = ('FAULTY', 'DAMAGED', 'SCRAP')


def kind_overview(model_class, category_q=None, with_empty=False):
    """Total / in-stock / sold / per-store / faulty-damaged counts for one
    dashboard card. `category_q` narrows a shared model (Spare) to one
    sub-category, as the 19 split-out spare cards do."""
    from apps.inventory.models import InventoryTransaction

    latest = InventoryTransaction.objects.filter(
        product=OuterRef('product')
    ).order_by('-created_at')
    qs = model_class.objects.annotate(
        latest_type=Subquery(latest.values('transaction_type')[:1]),
        latest_status=Subquery(latest.values('stock_status')[:1]),
        latest_store=Subquery(latest.values('store_location')[:1]),
    )
    if category_q is not None:
        qs = qs.filter(category_q)

    in_stock_qs = qs.exclude(latest_type='OUT')
    is_out = Q(latest_type='OUT')
    is_in = Q(latest_type__isnull=True) | ~Q(latest_type='OUT')  # same rows as the exclude() above

    # One aggregate query instead of five separate counts — the dashboard
    # builds ~45 cards, so this is what keeps it fast.
    counts = qs.aggregate(
        total=Count('id'),
        sold=Count('id', filter=is_out),
        faulty_damaged_in_stock=Count('id', filter=is_in & Q(latest_status__in=FAULTY_DAMAGED)),
        faulty_damaged_scrap_out=Count('id', filter=is_out & Q(latest_status__in=FAULTY_DAMAGED_SCRAP)),
    )

    by_store = list(
        in_stock_qs.exclude(latest_store='').exclude(latest_store__isnull=True)
        .values('latest_store').annotate(count=Count('id')).order_by('-count')
    )

    data = {
        'total': counts['total'],
        'in_stock': counts['total'] - counts['sold'],
        'sold': counts['sold'],
        'by_store': [{'store': r['latest_store'], 'count': r['count']} for r in by_store],
        'faulty_damaged_in_stock': counts['faulty_damaged_in_stock'],
        'faulty_damaged_scrap_out': counts['faulty_damaged_scrap_out'],
    }
    if with_empty:
        # Servers only: in-stock machines failing their group's Empty rule.
        from apps.servers.groups import annotate_empty
        data['empty_in_stock'] = annotate_empty(in_stock_qs).filter(is_empty=True).count()
    return data


def _build_registry():
    """Every dashboard card: label/icon/model (+ optional category_q) and the
    URLs its "View list / sold / faulty" links in the modal should point to.
    Built lazily (inside a function) to dodge import-order issues between
    apps.core, apps.categories and apps.servers.
    """
    from apps.categories.models import Card, Controller, CPU, HardDisk, Memory, NetworkingSpare, RailKit, SFP, Spare
    from apps.categories.spare_subcategories import SPARE_SUBCATEGORIES, spare_kind_key, spare_subcategory_q
    from apps.servers.models import Server

    registry = OrderedDict()
    registry['card'] = {'label': 'Card', 'icon': 'bi-credit-card', 'model': Card,
                        'list_url': ('card_list', []), 'sold_url': ('inventory_sold', ['card']), 'faulty_url': ('inventory_faulty', ['card'])}
    registry['cpu'] = {'label': 'CPU', 'icon': 'bi-cpu', 'model': CPU,
                       'list_url': ('cpu_list', []), 'sold_url': ('inventory_sold', ['cpu']), 'faulty_url': ('inventory_faulty', ['cpu'])}
    registry['controller'] = {'label': 'Controller', 'icon': 'bi-hdd-rack', 'model': Controller,
                              'list_url': ('controller_list', []), 'sold_url': ('inventory_sold', ['controller']), 'faulty_url': ('inventory_faulty', ['controller'])}
    from django.db.models import Q
    registry['harddisk_25'] = {'label': 'Hard Disk 2.5"', 'icon': 'bi-hdd', 'model': HardDisk,
                               'category_q': Q(size='2.5'),
                               'list_url': ('harddisk_25_list', []), 'sold_url': ('inventory_sold', ['harddisk_25']), 'faulty_url': ('inventory_faulty', ['harddisk_25'])}
    registry['harddisk_35'] = {'label': 'Hard Disk 3.5"', 'icon': 'bi-hdd-fill', 'model': HardDisk,
                               'category_q': Q(size='3.5'),
                               'list_url': ('harddisk_35_list', []), 'sold_url': ('inventory_sold', ['harddisk_35']), 'faulty_url': ('inventory_faulty', ['harddisk_35'])}
    registry['memory'] = {'label': 'Memory', 'icon': 'bi-memory', 'model': Memory,
                          'list_url': ('memory_list', []), 'sold_url': ('inventory_sold', ['memory']), 'faulty_url': ('inventory_faulty', ['memory'])}
    registry['networking_spare'] = {'label': 'Networking Spare', 'icon': 'bi-ethernet', 'model': NetworkingSpare,
                                    'list_url': ('networking_spare_list', []), 'sold_url': ('inventory_sold', ['networking_spare']), 'faulty_url': ('inventory_faulty', ['networking_spare'])}
    registry['railkit'] = {'label': 'Rail Kit', 'icon': 'bi-layout-sidebar', 'model': RailKit,
                           'list_url': ('railkit_list', []), 'sold_url': ('inventory_sold', ['railkit']), 'faulty_url': ('inventory_faulty', ['railkit'])}
    registry['sfp'] = {'label': 'SFP', 'icon': 'bi-router', 'model': SFP,
                       'list_url': ('sfp_list', []), 'sold_url': ('inventory_sold', ['sfp']), 'faulty_url': ('inventory_faulty', ['sfp'])}
    from apps.servers.groups import SERVER_GROUPS
    for slug, cfg in SERVER_GROUPS.items():
        registry[f'server_{slug}'] = {
            'label': cfg['label'], 'icon': cfg['icon'], 'model': Server,
            'category_q': Q(group=slug),
            'is_server': True,
            'list_url': ('server_group_list', [slug]),
            'empty_url': ('server_group_empty_list', [slug]),
            'sold_url': ('server_group_out_list', [slug]),
            'faulty_url': ('server_group_faulty_list', [slug]),
        }
    for slug, cfg in SPARE_SUBCATEGORIES.items():
        kind = spare_kind_key(slug)
        registry[kind] = {
            'label': cfg['label'], 'icon': cfg['icon'], 'model': Spare,
            'category_q': spare_subcategory_q(slug),
            'list_url': ('spare_subcategory_list', [kind]),
            'sold_url': ('inventory_sold', [kind]),
            'faulty_url': ('inventory_faulty', [kind]),
        }
    return registry


_REGISTRY = None


def dashboard_registry():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def card_data(kind, with_urls=False):
    """Overview dict for one card, plus (if requested) its resolved list/sold/
    faulty URLs — used by both the dashboard page and the detail-modal endpoint."""
    from django.urls import reverse

    cfg = dashboard_registry().get(kind)
    if not cfg:
        return None
    data = kind_overview(cfg['model'], cfg.get('category_q'), with_empty=cfg.get('is_server', False))
    data.update({'kind': kind, 'label': cfg['label'], 'icon': cfg['icon']})
    if with_urls:
        for key in ('list_url', 'sold_url', 'faulty_url', 'empty_url'):
            if key in cfg:
                name, args = cfg[key]
                data[key] = reverse(name, args=args)
    return data
