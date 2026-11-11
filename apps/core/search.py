"""One search for every list page: look in every text column.

`search_q(query, lookups)` splits what the user typed into words; every word
must appear in at least one of the columns (case-insensitive). So "600GB SAS"
finds 600 GB SAS disks, and "Rack 42" still finds that location.

Column lists are built from the models themselves (every CharField /
TextField), so a field added to a model later is searchable automatically.
"""
from django.db import models
from django.db.models import Q

# Reverse one-to-one names from Product to each inventory table.
CATEGORY_ATTRS = ('spare', 'card', 'cpu', 'controller', 'memory', 'sfp', 'railkit', 'harddisk', 'networking_spare', 'server')

PRODUCT_LOOKUPS = ('name', 'serial_no', 'part_no', 'brand', 'model', 'category__name')


def text_fields(model, prefix=''):
    """Every text column of a model, as lookups (optionally under a prefix)."""
    return [
        f'{prefix}{field.name}'
        for field in model._meta.concrete_fields
        if isinstance(field, (models.CharField, models.TextField))
    ]


def item_lookups(model, prefix=''):
    """Columns for a list of one inventory table (HardDisk, Spare, Server ...):
    its own text columns, its brand's name and its product's columns."""
    lookups = text_fields(model, prefix)
    names = {field.name for field in model._meta.concrete_fields}
    if 'brand' in names and isinstance(model._meta.get_field('brand'), models.ForeignKey):
        lookups.append(f'{prefix}brand__name')
    if 'product' in names:
        lookups += [f'{prefix}product__{p}' for p in PRODUCT_LOOKUPS]
    return lookups


def product_lookups(prefix=''):
    """Columns for a list of Products of any kind (stock-out status, frozen,
    rentals ...): the product's own columns plus the identifying columns of
    whichever inventory table it lives in (barcode, part no, location ...)."""
    from apps.categories.models import (
        CPU, SFP, Card, Controller, HardDisk, Memory, NetworkingSpare, RailKit, Spare,
    )
    from apps.servers.models import Server, ServerComponent

    tables = dict(zip(CATEGORY_ATTRS, (Spare, Card, CPU, Controller, Memory, SFP, RailKit, HardDisk, NetworkingSpare, Server)))
    wanted = {'barcode', 'tray_barcode', 'part_no', 'alt_part_no', 'model', 'oem_model_no', 'brand_model_no',
              'location', 'reference_location', 'service_tag', 'machine_no', 'capacity', 'size'}
    lookups = [f'{prefix}{p}' for p in PRODUCT_LOOKUPS]
    for attr, model in tables.items():
        lookups += [f'{prefix}{attr}__{name}' for name in text_fields(model) if name in wanted]
    lookups += [f'{prefix}server_component__{name}' for name in ('barcode', 'spare_type', 'part_no')
                if name in {f.name for f in ServerComponent._meta.concrete_fields}]
    return lookups


def search_q(query, lookups):
    """Q: every word of `query` is found in at least one of `lookups`."""
    condition = Q()
    for word in (query or '').split():
        any_column = Q()
        for lookup in lookups:
            any_column |= Q(**{f'{lookup}__icontains': word})
        condition &= any_column
    return condition


# Per-row computed columns that list pages show (Store, Status, Client,
# Invoice, OLF/DC, "Installed in" ...). Searched whenever the queryset has them.
SEARCHABLE_ANNOTATIONS = (
    'latest_location', 'latest_store', 'latest_status', 'latest_client', 'latest_invoice',
    'latest_olf_dc', 'server_label', 'server_service_tag', 'server_model_label',
)


def apply_search(queryset, query, lookups, distinct=False):
    query = (query or '').strip()
    if not query:
        return queryset
    present = queryset.query.annotations
    lookups = list(lookups) + [a for a in SEARCHABLE_ANNOTATIONS if a in present and a not in lookups]
    queryset = queryset.filter(search_q(query, lookups))
    return queryset.distinct() if distinct else queryset
