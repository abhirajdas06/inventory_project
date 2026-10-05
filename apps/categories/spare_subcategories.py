"""Splits the old single "common Spare" bucket into 19 named sub-categories.

Nothing about the underlying data changes: every item here is still a plain
`Spare` row (same fields, same stock in/out logic) — this module only says
which `SpareCategory.name` values belong to which sub-category, so the nav,
list/sold/faulty pages, imports and dashboard can show them separately.

``match`` is the set of category-name spellings seen in real data (including
known typos from years of free-text entry, e.g. "COOILING FAN"). A category
name not covered by ANY explicit set falls into 'miscellaneous' — the
catch-all — so nothing is ever silently dropped from the Spare lists.

To add a spelling variant later: add it to that sub-category's ``match`` set.
To add a brand-new sub-category: add an entry here (before the 'miscellaneous'
one, order doesn't matter functionally but controls nav/dashboard order) —
the import options, list/sold/faulty pages and dashboard card are generated
from this dict automatically; nothing elsewhere needs to change.
"""
from collections import OrderedDict

from django.db.models import Q

SPARE_SUBCATEGORIES = OrderedDict([
    ('cable', {
        'label': 'Cable', 'canonical': 'CABLE', 'icon': 'bi-usb-plug-fill',
        'match': {'CABLE', 'FIBER CABLE', 'SAS CABLE'},
    }),
    ('adaptor', {
        'label': 'Adaptor', 'canonical': 'ADAPTOR', 'icon': 'bi-plug-fill',
        'match': {'ADAPTOR'},
    }),
    ('battery', {
        'label': 'Battery', 'canonical': 'BATTERY', 'icon': 'bi-battery-half',
        'match': {'BATTERY'},
    }),
    ('cache_memory', {
        'label': 'Cache Memory', 'canonical': 'CACHE MEMORY', 'icon': 'bi-memory',
        'match': {'CACHE MEMORY'},
    }),
    ('cooling_fan_backplane', {
        'label': 'Cooling Fan Backplane', 'canonical': 'COOLING FAN BACKPLANE', 'icon': 'bi-fan',
        'match': {'COOLING FAN BACKPLANE'},
    }),
    ('cooling_fan', {
        'label': 'Cooling Fan', 'canonical': 'COOLING FAN', 'icon': 'bi-fan',
        'match': {'COOLING FAN', 'COOILING FAN', 'COOLINGFAN'},
    }),
    ('optical_drive', {
        'label': 'Optical Drive', 'canonical': 'OPTICAL DRIVE', 'icon': 'bi-disc',
        'match': {'OPTICAL DRIVE', 'DVD', 'DVD DRIVE', 'DVD-ROM'},
    }),
    ('hard_disk_backplane', {
        'label': 'Hard Disk Backplane', 'canonical': 'HARD DISK BACKPLANE', 'icon': 'bi-hdd-stack-fill',
        'match': {
            'HARD DISK BACKPLANE', 'HARDDISK BACKPLANE', 'HARDDISK  BACKPLANE',
            'EXPANDER', 'EXPANSION BOARD', 'MIDPLANE BOARD',
        },
    }),
    ('heatsink', {
        'label': 'Heatsink', 'canonical': 'HEATSINK', 'icon': 'bi-thermometer-high',
        'match': {'HEATSINK', 'HEAT SINK'},
    }),
    ('io_board', {
        'label': 'IO Board', 'canonical': 'IO BOARD', 'icon': 'bi-motherboard-fill',
        # Passthru cards and processor boards are grouped under IO Board per spec.
        'match': {'IO BOARD', 'PASSTHRU CARD', 'PROCESSOR BOARD'},
    }),
    ('ip_phone', {
        'label': 'IP Phone', 'canonical': 'IP PHONE', 'icon': 'bi-telephone-fill',
        'match': {'IP PHONE', 'IP PHONES'},
    }),
    ('miscellaneous', {
        'label': 'Miscellaneous', 'canonical': 'MISCELLANEOUS', 'icon': 'bi-box-seam-fill',
        # Catch-all: match=None means "everything not claimed by another sub-category".
        'match': None,
    }),
    ('motherboard', {
        'label': 'Motherboard', 'canonical': 'MOTHER BOARD', 'icon': 'bi-cpu-fill',
        'match': {'MOTHER BOARD', 'MOTHERBOARD'},
    }),
    ('on_off_switch', {
        'label': 'On/Off Switch', 'canonical': 'ON OFF SWITCH', 'icon': 'bi-toggle2-on',
        'match': {'ON OFF SWITCH', 'SERVER FRONT PANEL', 'SERVER LEFT EAR', 'SERVER RIGHT EAR'},
    }),
    ('power_backplane', {
        'label': 'Power Backplane', 'canonical': 'POWER BACKPLANE', 'icon': 'bi-lightning-charge-fill',
        'match': {'POWER BACKPLANE'},
    }),
    ('power_cage', {
        'label': 'Power Cage', 'canonical': 'POWER CAGE', 'icon': 'bi-battery-charging',
        'match': {'POWER CAGE'},
    }),
    ('power_supply', {
        'label': 'Power Supply', 'canonical': 'POWER SUPPLY', 'icon': 'bi-plug-fill',
        'match': {'POWER SUPPLY', 'POWERSUPPLY'},
    }),
    ('riser_card', {
        'label': 'Riser Card', 'canonical': 'RISER CARD', 'icon': 'bi-gpu-card',
        'match': {'RISER CARD'},
    }),
    ('vrm', {
        'label': 'VRM', 'canonical': 'VRM', 'icon': 'bi-lightning-fill',
        'match': {'VRM'},
    }),
])

# Category names that belong to a DEDICATED product model (Card, CPU/
# Processor, Memory, SFP, Hard Disk) but were entered as generic Spare rows
# instead — almost always because they're a Controller's child component
# (recorded via Spare.controller, which only the generic Spare model
# supports). These are excluded from every spare sub-category, including
# Miscellaneous: moving the actual rows into Card/CPU/Memory/SFP/HardDisk
# would break that controller link, so instead each of those 5 dedicated
# list pages shows them in a "Also recorded as Spare" section — see
# apps.categories.views.dedicated_lookalike_spares. Not excluding CABINET:
# it has no dedicated model to show it on instead, so it stays in
# Miscellaneous.
DEDICATED_LOOKALIKE_CATEGORIES = {
    'CARD': 'card_list',
    'PROCESSOR': 'cpu_list',
    'HARD DISK': 'harddisk_list',
    'MEMORY': 'memory_list',
    'SFP': 'sfp_list',
}

# Every explicitly-claimed category name, across all sub-categories — used to
# build the 'miscellaneous' catch-all (anything NOT in this set).
_EXPLICIT_MATCHES = set(DEDICATED_LOOKALIKE_CATEGORIES)
for _cfg in SPARE_SUBCATEGORIES.values():
    if _cfg['match']:
        _EXPLICIT_MATCHES |= _cfg['match']


def spare_subcategory_q(slug):
    """Q object (on a Spare/Product queryset) selecting this sub-category's rows."""
    cfg = SPARE_SUBCATEGORIES[slug]
    if cfg['match'] is None:
        return ~Q(product__category__name__in=_EXPLICIT_MATCHES)
    return Q(product__category__name__in=cfg['match'])


def spare_kind_key(slug):
    return f'spare_{slug}'


# The LIST_MODELS / import model_key used for each sub-category, e.g. 'spare_cable'.
SPARE_KIND_KEYS = [spare_kind_key(slug) for slug in SPARE_SUBCATEGORIES]
