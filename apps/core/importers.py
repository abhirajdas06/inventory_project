from datetime import date, datetime

from django.db import transaction
from django.db.models import Q
from openpyxl import load_workbook

from apps.categories.models import ImportJob, NetworkingSpare
from apps.categories.spare_subcategories import SPARE_SUBCATEGORIES, spare_kind_key
from apps.core.activity import log_activity, log_timeline
from apps.core.models import Brand, Product, SpareCategory
from apps.core.services import (
    add_server_component,
    create_product_and_card,
    create_product_and_cpu,
    create_product_and_harddisk,
    create_product_and_memory,
    create_product_and_railkit,
    create_product_and_sfp,
    create_product_and_spare,
    create_server_with_components,
)
from apps.inventory.models import NAME_ONLY_STOCK_OUT, STOCK_OUT_ONLY_STATUSES, InventoryTransaction, normalize_stock_status
from apps.servers.models import Server


DEFAULT_STORE = 'WH1'
DEFAULT_STATUS = 'LIVE'
# Statuses a row can be STOCKED IN with (In-House Use / Return to Vendor are stock-out only).
VALID_STOCK_STATUSES = {value for value, _ in InventoryTransaction.STOCK_STATUS} - STOCK_OUT_ONLY_STATUSES


IMPORT_LABELS = {
    'battery': 'Spares',
    'card': 'Card',
    'controller': 'Controller',
    'cpu': 'CPU',
    'harddisk': 'Hard Disk',
    'memory': 'Memory',
    'networking_spare': 'Networking Spare',
    'railkit': 'Rail Kit',
    'server': 'Server',
    'sfp': 'SFP',
    'stock_out': 'Stock Out',
}


HEADER_MAPS = {
    'battery': {
        'Product': 'category',
        'Brand': 'brand',
        'Model': 'model',
        'Part No': 'part_no',
        'Alt Part No': 'alt_part_no',
        'Serial No': 'serial_no',
        'Alt Serial. no': 'alt_serial_no',
        'Specs': 'specs',
        'QTY': 'qty',
        'Barcode No': 'barcode',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Remark(describe exact issue)': 'remark',
    },
    'card': {
        'Brand': 'brand',
        'OEM': 'oem',
        'Brand Model No': 'brand_model_no',
        'Interface(Sas/Sata/Fc/Scsi)': 'interface',
        'Part No': 'part_no',
        'Alt Part No': 'alt_part_no',
        'Brand Serial no 1': 'brand_serial_no_1',
        'Capacity': 'capacity',
        'Port': 'port',
        'Barcode': 'barcode',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Remarks': 'remark',
    },
    'controller': {
        'Sr.No': 'import_group',
        'Brand': 'brand',
        'Product Category': 'spare_type',
        'Product': 'product_name',
        'Model': 'model',
        'Part No': 'part_no',
        'Alt Part No': 'alt_part_no',
        'Serial No': 'serial_no',
        'Alt Serial. no': 'alt_serial_no',
        'Specs': 'specs',
        'QTY': 'qty',
        'Barcode No': 'barcode',
        'LOCATION': 'location',
        'Reference Location': 'reference_location',
        'Parent-child Location': 'parent_child_location',
        'Remark(describe exact issue)': 'remark',
    },
    'cpu': {
        'Brand': 'brand',
        'Model': 'model',
        'Part No': 'part_no',
        'No of Cores': 'no_of_cores',
        'No of Threads': 'no_of_threads',
        'GHZ': 'ghz',
        'Frequency': 'frequency',
        'Cache': 'cache',
        'Barcode': 'barcode',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Remark': 'remark',
    },
    'harddisk': {
        'Brand': 'brand',
        'OEM': 'oem',
        'Brand Model No': 'brand_model_no',
        'OEM Model No': 'oem_model_no',
        'Capacity': 'capacity',
        'RPM': 'rpm',
        'Interface(Sas/Sata/Fc)': 'interface',
        'Part No': 'part_no',
        'Alt Part no': 'alt_part_no',
        'Alt Fru No / Alt Part No (1)': 'alt_fru_1',
        'Alt Fru No / Alt Part No (2)': 'alt_fru_2',
        'Alt Fru No / Alt Part No (3)': 'alt_fru_3',
        'Retail Part No(Box Pack)': 'retail_part_no',
        'Spare Part No-Tray': 'spare_part_tray',
        'GPN Code': 'gpn_code',
        'Brand Serial no 1': 'brand_serial_no',
        'Oem Serial no': 'oem_serial_no',
        'Serial No': 'serial_no',
        'Firmware': 'firmware',
        'Size(2.5/3.5)': 'size',
        'Health': 'health',
        'GB/S': 'gb_s',
        'Barcode': 'barcode',
        'Tray -Barcode': 'tray_barcode',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Remark': 'remark',
    },
    'memory': {
        'Brand': 'brand',
        'OEM': 'oem',
        'Model': 'model',
        'Part No 1': 'part_no_1',
        'Part No 2': 'part_no_2',
        'Part No 3': 'part_no_3',
        'Size': 'size',
        'Ram Type(Ecc Regd/Fb Dimm )': 'ram_type',
        'DDR Version(PC)': 'ddr_version',
        'Frequency': 'frequency',
        'Rank': 'rank',
        'Serial No': 'serial_no',
        'QTY': 'qty',
        'Barcode': 'barcode',
        'Location': 'location',
        'Reference location': 'reference_location',
        'Remark': 'remark',
    },
    'networking_spare': {
        'Product': 'category',
        'Brand': 'brand',
        'Part no': 'part_no',
        'Alt Part No': 'alt_part_no',
        'Serial No': 'serial_no',
        'Alt Serial No': 'alt_serial_no',
        'Specs': 'specs',
        'QTY': 'qty',
        'Barcode No': 'barcode',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Remark (Describe exact Issue)': 'remark',
    },
    'railkit': {
        'Brand': 'brand',
        'Left/Right': 'side',
        'Part No': 'part_no',
        'Serial No': 'serial_no',
        'SPECS': 'specs',
        'Barcode': 'barcode',
        'Supported Model': 'supported_model',
        'QTY': 'qty',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Remark(describe exact issue)': 'remark',
    },
    'sfp': {
        'Brand': 'brand',
        'Model': 'model',
        'Part no': 'part_no',
        'Descripition': 'description',
        'Fibre type (SMF/MMF)': 'fibre_type',
        'Data Rate': 'data_rate',
        'Serial no': 'serial_no',
        'Barcode': 'barcode',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Remark': 'remark',
    },
    'server': {
        'Testing Date': 'testing_date',
        'Tested by/FE name': 'tested_by',
        'Machine Type': 'machine_type',
        'Machine no': 'machine_no',
        'System Service Tag No': 'service_tag',
        'Model': 'server_model',
        'Spares Type': 'spare_type',
        'Part No': 'part_no',
        'Alt Part No': 'alt_part_no',
        'Serial No': 'serial_no',
        'Alt Serial. No': 'alt_serial_no',
        'Specs': 'specs',
        'Barcode No': 'barcode',
        'QTY': 'qty',
        'Working/Not working': 'working_status',
        'Location': 'location',
        'Reference Location': 'reference_location',
        'Parent-child Location': 'parent_child_location',
        'Remark(describe exact issue)': 'remark',
    },
    'stock_out': {
        'Barcode No': 'barcode',
        'Client Name': 'client_name',
        'Invoice No': 'invoice_no',
        'OLF / DC No': 'olf_dc_number',
        'Stock Status': 'stock_status',
        'Stock Out Date': 'stock_out_date',
    },
}


# ════════════════════════════════════════════════════════════
#  SPARE SUB-CATEGORY IMPORTS — one option per split-out category
#  (Cable, Battery, Motherboard, ...). Same columns as the common
#  "Spares" import minus Product/category — the category is implied
#  by which import option was picked, so the sheet doesn't need it.
#
#  Miscellaneous is the one exception: it's a grab-bag of many distinct
#  product types (FRONT BEZEL, CARTRIDGE, KEYBOARD, MOUSE, ...), not a single
#  category, so — like the old common "Spares" import — it KEEPS the Product
#  column and stores each row's own value as its category, instead of
#  forcing every row to the literal text "MISCELLANEOUS". That value is only
#  a fallback for a row that leaves the column blank.
# ════════════════════════════════════════════════════════════
_SPARE_SUBCATEGORY_HEADERS = {k: v for k, v in HEADER_MAPS['battery'].items() if k != 'Product'}
for _slug, _cfg in SPARE_SUBCATEGORIES.items():
    HEADER_MAPS[spare_kind_key(_slug)] = (
        dict(HEADER_MAPS['battery']) if _slug == 'miscellaneous' else dict(_SPARE_SUBCATEGORY_HEADERS)
    )
    IMPORT_LABELS[spare_kind_key(_slug)] = _cfg['label']


# ════════════════════════════════════════════════════════════
#  HARD DISK SIZE IMPORTS — Hard Disk 2.5" / 3.5", same idea as the spare
#  sub-categories above but on the HardDisk model's own `size` field: same
#  columns as the common Hard Disk import minus Size(2.5/3.5), since the
#  import option itself decides it.
# ════════════════════════════════════════════════════════════
HARDDISK_SIZE_IMPORTS = {'harddisk_25': '2.5', 'harddisk_35': '3.5'}
_HARDDISK_SIZE_HEADERS = {k: v for k, v in HEADER_MAPS['harddisk'].items() if k != 'Size(2.5/3.5)'}
for _hdd_key, _hdd_label in (('harddisk_25', '2.5" Hard Disk'), ('harddisk_35', '3.5" Hard Disk')):
    HEADER_MAPS[_hdd_key] = dict(_HARDDISK_SIZE_HEADERS)
    IMPORT_LABELS[_hdd_key] = _hdd_label


# ════════════════════════════════════════════════════════════
#  SERVER GROUP IMPORTS — Blade Server, Storage, Networking Switch, ...
#  Exactly the Server import's columns; the option picked decides which
#  group (list) every server in the sheet goes into. Machine Type alone
#  can't tell e.g. Cisco from HP chassis, or a Sun rack server from any
#  other rack server — the generic "Server" import has to guess.
# ════════════════════════════════════════════════════════════
from apps.servers.groups import SERVER_GROUPS  # noqa: E402

SERVER_GROUP_IMPORTS = {f'server_{_slug}': _slug for _slug in SERVER_GROUPS}
for _srv_key, _srv_slug in SERVER_GROUP_IMPORTS.items():
    HEADER_MAPS[_srv_key] = dict(HEADER_MAPS['server'])
    IMPORT_LABELS[_srv_key] = SERVER_GROUPS[_srv_slug]['label']


# Snapshot which Excel columns are REQUIRED per model, BEFORE we merge in the
# optional "Stock In Status" column below. That column must never become a
# required header — otherwise every existing stock-in template (which
# doesn't have it) would suddenly fail with "Missing columns: ...".
REQUIRED_HEADERS = {key: set(headers) for key, headers in HEADER_MAPS.items()}


def _spare_subcategory_creator(canonical_category):
    """A CREATE_BY_KEY entry that stocks in a Spare with a fixed category —
    the sheet has no Product/category column, so the import option itself
    decides it."""
    def _create(data):
        return create_product_and_spare({**data, 'category': canonical_category})
    return _create


def _miscellaneous_creator(canonical_category):
    """Miscellaneous keeps the sheet's own Product column as the category
    (FRONT BEZEL, CARTRIDGE, KEYBOARD, ...) — only a row that leaves it blank
    falls back to the canonical "MISCELLANEOUS" text."""
    def _create(data):
        row = dict(data)
        row['category'] = (row.get('category') or '').strip() or canonical_category
        return create_product_and_spare(row)
    return _create


def _harddisk_size_creator(size):
    """A CREATE_BY_KEY entry that stocks in a Hard Disk with a fixed size —
    the sheet has no Size(2.5/3.5) column, so the import option decides it."""
    def _create(data):
        return create_product_and_harddisk({**data, 'size': size})
    return _create


CREATE_BY_KEY = {
    'battery': create_product_and_spare,
    'card': create_product_and_card,
    'cpu': create_product_and_cpu,
    'harddisk': create_product_and_harddisk,
    'memory': create_product_and_memory,
    'railkit': create_product_and_railkit,
    'sfp': create_product_and_sfp,
}
for _slug, _cfg in SPARE_SUBCATEGORIES.items():
    CREATE_BY_KEY[spare_kind_key(_slug)] = (
        _miscellaneous_creator(_cfg['canonical']) if _slug == 'miscellaneous'
        else _spare_subcategory_creator(_cfg['canonical'])
    )
for _hdd_key, _hdd_size in HARDDISK_SIZE_IMPORTS.items():
    CREATE_BY_KEY[_hdd_key] = _harddisk_size_creator(_hdd_size)


# ════════════════════════════════════════════════════════════
#  RE-IMPORT — update items whose barcode already exists
# ════════════════════════════════════════════════════════════
# Importing a stock-in sheet never fails on a barcode that is already in the
# system: that item's details are updated from the row instead (every column
# that has a value — a blank cell never wipes existing data). The store, the
# location, the reference location, the barcode and the stock status / history
# are left as they are; only a transfer or a stock movement changes those.
# New barcodes are stocked in as usual.
HARDDISK_IMPORT_KEYS = {'harddisk', 'harddisk_25', 'harddisk_35'}

# Older sheets (Sold / Rent / Open tabs) title some columns differently.
HEADER_ALIASES = {
    'harddisk': {
        'BRAND SERIAL NO': 'BRAND SERIAL NO 1',
        'SIZE': 'SIZE(2.5/3.5)',
        'SIZE (2.5/3.5)': 'SIZE(2.5/3.5)',
        'INTERFACE (SAS/SATA/FC)': 'INTERFACE(SAS/SATA/FC)',
    },
}

# Never changed by re-importing an existing barcode.
KEEP_ON_UPDATE = {
    'location', 'reference_location', 'parent_child_location', 'store_location', 'barcode', 'stock_status',
    'id', 'product', 'created_at', 'controller', 'server',
}
# Imports whose sheet carries the item's category (Product column).
CATEGORY_FROM_SHEET = {'spare_miscellaneous', 'networking_spare'}


def _alias_family(model_key):
    base = _base_key(model_key or '')
    return 'harddisk' if base in HARDDISK_IMPORT_KEYS else base


def _sheet_header(header, model_key):
    """Normalised sheet header, with known spelling variants mapped to the
    header the import expects."""
    key = _normalize_header(header)
    return HEADER_ALIASES.get(_alias_family(model_key), {}).get(key, key)


def _blank(value):
    return value is None or str(value).strip() == ''


def existing_product_by_barcode(barcode):
    """The Product whose inventory record (any category, or a server
    component) carries this barcode, else None."""
    from apps.categories.models import CPU, SFP, Card, Controller, HardDisk, Memory, NetworkingSpare, RailKit, Spare
    from apps.servers.models import Server, ServerComponent
    barcode = (barcode or '').strip()
    if not barcode:
        return None
    for model in (Spare, Card, CPU, Memory, SFP, RailKit, HardDisk, NetworkingSpare, Controller, Server, ServerComponent):
        obj = model.objects.filter(barcode__iexact=barcode).select_related('product').first()
        if obj is not None and obj.product_id:
            return obj.product
    return None


def _inventory_records(product):
    from apps.servers.models import ServerComponent
    records = []
    for attr in ('spare', 'card', 'cpu', 'controller', 'memory', 'sfp', 'railkit', 'harddisk', 'networking_spare', 'server'):
        try:
            obj = getattr(product, attr)
        except Exception:
            obj = None
        if obj is not None:
            records.append(obj)
    return records + list(ServerComponent.objects.filter(product=product))


# ── Auto-generated product names ───────────────────────────────────────────
# The same formulas the create functions in apps.core.services use, so a
# re-import that changes e.g. a hard disk's capacity or a card's model also
# renames the product ("HDD - 600GB SAS 2.5 - IBM (SEAGATE)" ...).

def _txt(value):
    return '' if value is None else str(value).strip()


def product_name_parts(product):
    """(auto name, {part: value}) for a product, by what kind of item it is."""
    from apps.servers.models import ServerComponent

    def brand_of(obj):
        brand = getattr(obj, 'brand', None)
        return brand.name if brand is not None and hasattr(brand, 'name') else _txt(product.brand).upper()

    component = ServerComponent.objects.filter(product=product).first()
    if component is not None:
        parts = {'spare_type': _txt(component.spare_type).upper(), 'barcode': _txt(component.barcode), 'brand': _txt(product.brand).upper()}
        return f"Server - {parts['spare_type']} - {parts['barcode']} - {parts['brand']}".strip(' -').replace('  ', ' '), parts

    def record(attr):
        try:
            return getattr(product, attr)
        except Exception:
            return None

    server = record('server')
    if server is not None:
        parts = {'model': _txt(server.model), 'service_tag': _txt(server.service_tag)}
        return f"SERVER - {parts['model']} - {parts['service_tag']}".strip(' -'), parts
    controller = record('controller')
    if controller is not None:
        parts = {'model': _txt(controller.model), 'brand': brand_of(controller)}
        return f"CONTROLLER - {parts['model']} - {parts['brand']}".strip(' -'), parts
    disk = record('harddisk')
    if disk is not None:
        parts = {'capacity': _txt(disk.capacity), 'interface': _txt(disk.interface), 'size': _txt(disk.size),
                 'brand': brand_of(disk), 'oem': _txt(disk.oem)}
        name = (f"HDD - {parts['capacity']} {parts['interface']} {parts['size']} - {parts['brand']} ({parts['oem']})"
                .strip().strip('()').replace('  ', ' '))
        return name, parts
    memory = record('memory')
    if memory is not None:
        parts = {'size': _txt(memory.size), 'ddr_version': _txt(memory.ddr_version), 'brand': brand_of(memory), 'oem': _txt(memory.oem)}
        return f"MEMORY - {parts['size']} {parts['ddr_version']} - {parts['brand']} ({parts['oem']})", parts
    sfp = record('sfp')
    if sfp is not None:
        parts = {'model': _txt(sfp.model), 'data_rate': _txt(sfp.data_rate), 'brand': brand_of(sfp)}
        return f"SFP - {parts['model']} - {parts['data_rate']} - {parts['brand']}".strip(' -'), parts
    railkit = record('railkit')
    if railkit is not None:
        parts = {'brand': brand_of(railkit), 'side': _txt(railkit.side), 'supported_model': _txt(railkit.supported_model)}
        return f"RAILKIT - {parts['brand']} - {parts['side']} - {parts['supported_model']}".strip(' -'), parts
    card = record('card')
    if card is not None:
        parts = {'brand_model_no': _txt(card.brand_model_no), 'brand': brand_of(card)}
        return f"CARD - {parts['brand_model_no']} - {parts['brand']}", parts
    cpu = record('cpu')
    if cpu is not None:
        parts = {'model': _txt(cpu.model), 'brand': brand_of(cpu)}
        return f"PROCESSOR - {parts['model']} - {parts['brand']}", parts
    networking = record('networking_spare')
    category = product.category.name if product.category_id else ''
    if networking is not None:
        parts = {'category': category, 'brand': brand_of(networking), 'part_no': _txt(networking.part_no)}
        return f"{parts['category']} - {parts['brand']} - {parts['part_no']}".strip(' -'), parts
    spare = record('spare')
    if spare is not None:
        parts = {'category': category, 'model': _txt(spare.model), 'brand': brand_of(spare)}
        if spare.controller_id:
            return f"CONTROLLER - {parts['category']} - {parts['model']} - {parts['brand']}".strip(' -'), parts
        return f"{parts['category']} - {parts['model']} - {parts['brand']}", parts
    return product.name, {}


def _fresh(product):
    return Product.objects.select_related(
        'category', *[f'{a}__brand' for a in ('spare', 'card', 'cpu', 'controller', 'memory', 'sfp', 'railkit', 'harddisk', 'networking_spare')],
        'server').get(pk=product.pk)


def refresh_product_name(product, before):
    """After an update: if any part of the auto name changed, rename the product.
    ``before`` is product_name_parts() taken before the update.

    A name that is still the auto-generated one is rebuilt in full. A name
    that was typed in or came from an older format keeps its wording, with
    each changed value swapped in place (e.g. the old barcode -> the new one).
    Returns the new name, or None when nothing changed."""
    import re
    old_name, old_parts = before
    new_name, new_parts = product_name_parts(_fresh(product))
    changed = {k: (old_parts.get(k, ''), v) for k, v in new_parts.items() if old_parts.get(k, '') != v}
    if not changed:
        return None
    current = product.name or ''
    norm = lambda text: ' '.join(text.split()).upper()
    if norm(current) == norm(old_name) or not current.strip():
        renamed = new_name
    else:
        renamed = current
        for old, new in changed.values():
            if old:
                renamed = re.sub(r'(?<!\w)' + re.escape(old) + r'(?!\w)', lambda _m, _new=new: _new, renamed, flags=re.IGNORECASE)
        renamed = ' '.join(renamed.split())
    renamed = renamed[:255]
    if renamed and renamed != current:
        Product.objects.filter(pk=product.pk).update(name=renamed)
        product.name = renamed
        return renamed
    return None


def update_existing_from_row(product, row, model_key):
    """Update an existing item's details from an import row (non-blank cells
    only; never store, location, reference location, barcode or stock status).
    Returns the list of changed fields."""
    from django.db import models as dj_models
    name_before = product_name_parts(_fresh(product))
    base = _base_key(model_key)
    data = dict(row)
    if base in HARDDISK_SIZE_IMPORTS:
        data['size'] = HARDDISK_SIZE_IMPORTS[base]
    changed = []
    for obj in _inventory_records(product):
        fields = {f.name: f for f in obj._meta.concrete_fields}
        update = []
        for key, value in data.items():
            if key in KEEP_ON_UPDATE or key not in fields or _blank(value):
                continue
            field = fields[key]
            if field.is_relation:
                if key == 'brand':
                    brand, _ = Brand.objects.get_or_create(name=str(value).strip().upper())
                    if obj.brand_id != brand.id:
                        obj.brand = brand
                        update.append(key)
                continue
            if isinstance(field, (dj_models.IntegerField, dj_models.DecimalField, dj_models.FloatField)):
                try:
                    value = int(float(value))
                except (TypeError, ValueError):
                    continue
            elif isinstance(field, (dj_models.DateField, dj_models.BooleanField)):
                continue
            else:
                value = str(value).strip()
                if field.max_length:
                    value = value[:field.max_length]
            if getattr(obj, key) != value:
                setattr(obj, key, value)
                update.append(key)
        if update:
            obj.save(update_fields=update)
            changed += [f'{type(obj).__name__}.{f}' for f in update]

    product_update = []
    serial = (data.get('serial_no') or '').strip().upper()
    model_name = data.get('model') or data.get('oem_model_no') or data.get('brand_model_no')
    for field, value in (('serial_no', serial), ('part_no', data.get('part_no')), ('model', model_name),
                         ('brand', (data.get('brand') or '').strip().upper())):
        if not _blank(value) and getattr(product, field) != str(value).strip():
            setattr(product, field, str(value).strip()[:100])
            product_update.append(field)
    category = (data.get('category') or '').strip().upper()
    if base in CATEGORY_FROM_SHEET and category and product.category.name != category:
        product.category, _ = SpareCategory.objects.get_or_create(name=category)
        product_update.append('category')
    if product_update:
        product.save(update_fields=product_update)
        changed += [f'Product.{f}' for f in product_update]
    if changed and refresh_product_name(product, name_before):
        changed.append('Product.name')
    return changed


def _update_server_fields(row):
    """Server import: the machine's own columns (type, machine no, model,
    tested by) when its System Service Tag is already in the system."""
    service_tag = (row.get('service_tag') or '').strip().upper()
    server = Server.objects.filter(service_tag=service_tag).first() if service_tag else None
    if server is None:
        return
    name_before = product_name_parts(_fresh(server.product)) if server.product_id else None
    update = []
    for field, value in (('machine_type', row.get('machine_type')), ('machine_no', row.get('machine_no')),
                         ('model', row.get('server_model')), ('tested_by', row.get('tested_by'))):
        if not _blank(value) and getattr(server, field) != str(value).strip():
            setattr(server, field, str(value).strip())
            update.append(field)
    if update:
        server.save(update_fields=update)
        if name_before is not None:
            refresh_product_name(server.product, name_before)


# ════════════════════════════════════════════════════════════
#  STOCK OUT IMPORT — per category
#
#  Every inventory category gets a "<key>_stock_out" import that
#  reuses the EXACT Stock In template columns and appends the
#  Stock Out columns at the end. One row → create product +
#  stock in + immediate stock out.
#
#  The appended targets are prefixed `so_` so they never collide
#  with the Stock In field names (especially stock_status).
# ════════════════════════════════════════════════════════════
STOCK_OUT_APPEND_COLUMNS = {
    'Client Name': 'so_client_name',
    'Invoice No': 'so_invoice_no',
    'OLF / DC No': 'so_olf_dc_number',
    'Stock Status': 'so_stock_status',
    'Stock Out Date': 'so_stock_out_date',
}

# Categories that support combined stock-out import (everything that
# creates inventory). New inventory models added here are picked up
# automatically.
STOCK_OUT_BASE_KEYS = [
    'battery', 'card', 'cpu', 'harddisk', 'memory',
    'railkit', 'sfp', 'networking_spare', 'controller', 'server',
] + [spare_kind_key(_slug) for _slug in SPARE_SUBCATEGORIES] + list(HARDDISK_SIZE_IMPORTS) + list(SERVER_GROUP_IMPORTS)

# Optional "Stock In Status" column, added to every Stock-In template (and
# inherited by the combined Stock-In + Stock-Out templates below). It is NOT
# required — if the column or a cell is missing/blank the row defaults to
# LIVE as before. If it holds a recognized status (e.g. FAULTY, DAMAGED) the
# row is stocked in with that status instead, and it still counts as "in
# stock" — only a Stock Out transaction removes an item from the active list.
STOCK_IN_STATUS_COLUMN = {'Stock In Status': 'stock_status'}
for _base_key in STOCK_OUT_BASE_KEYS:
    HEADER_MAPS[_base_key] = {**HEADER_MAPS[_base_key], **STOCK_IN_STATUS_COLUMN}

for _base_key in STOCK_OUT_BASE_KEYS:
    _combined_key = f'{_base_key}_stock_out'
    REQUIRED_HEADERS[_combined_key] = REQUIRED_HEADERS[_base_key] | set(STOCK_OUT_APPEND_COLUMNS)
    HEADER_MAPS[_combined_key] = {
        **HEADER_MAPS[_base_key],
        **STOCK_OUT_APPEND_COLUMNS,
    }
    IMPORT_LABELS[_combined_key] = f'{IMPORT_LABELS[_base_key]} — Stock Out'


def clean_value(value):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def normalize_qty(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 1


def _normalize_header(value):
    """Case/whitespace-insensitive key for matching an Excel column header to
    the header map. Real warehouse sheets are hand-typed over years, so the
    same column shows up as "QTY", "Qty", "Part No" / "Part no" etc — we
    still want those recognised rather than rejected as a missing column."""
    return ' '.join(str(value or '').split()).upper()


def _base_key(model_key):
    return model_key[:-len('_stock_out')] if model_key.endswith('_stock_out') else model_key


def select_sheet(wb, model_key=None):
    """Pick the worksheet to import.

    The nightly export is ONE workbook with a sheet per category, named after
    the import label (Memory, Rail Kit, Server ...). So when the workbook has
    several sheets we import the one matching the selected import type; a
    single-sheet (or unmatched) workbook falls back to the active sheet, which
    keeps every existing hand-made template working.
    """
    if model_key and len(wb.sheetnames) > 1:
        label = IMPORT_LABELS.get(_base_key(model_key), '').strip().lower()
        for name in wb.sheetnames:
            if name.strip().lower() == label:
                return wb[name]
    return wb.active


def read_headers(path, model_key=None):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = select_sheet(wb, model_key)
    return [clean_value(c.value) for c in next(ws.iter_rows(min_row=1, max_row=1))]


def count_rows(path, model_key=None):
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = select_sheet(wb, model_key)
    total = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if any(clean_value(v) for v in row):
            total += 1
    return total


def start_import_job(model_key, upload, user, store_location=None):
    if model_key not in HEADER_MAPS:
        raise ValueError('Unknown import model')

    job = ImportJob.objects.create(
        model_key=model_key,
        upload=upload,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
        status='PENDING',
        store_location=(store_location or DEFAULT_STORE).strip().upper(),
    )

    try:
        headers = read_headers(job.upload.path, model_key)
    except Exception as exc:
        job.status = 'FAILED'
        job.errors = [{'row': 1, 'error': f'Could not read the Excel file: {exc}'}]
        job.save(update_fields=['status', 'errors'])
        _notify_import_failure(job, job.errors[0]['error'])
        raise ValueError(job.errors[0]['error'])
    expected = REQUIRED_HEADERS.get(model_key, set(HEADER_MAPS[model_key]))
    if model_key == 'stock_out':
        expected = {'Barcode No'}  # the other five columns are optional (blank -> Sale / today)
    present = {_sheet_header(h, model_key) for h in headers}
    missing = sorted(h for h in expected if _normalize_header(h) not in present)
    if missing:
        job.status = 'FAILED'
        job.errors = [{'row': 1, 'error': f"Missing columns: {', '.join(missing)}"}]
        job.save(update_fields=['status', 'errors'])
        _notify_import_failure(job, job.errors[0]['error'])
        raise ValueError(job.errors[0]['error'])

    job.total_rows = count_rows(job.upload.path, model_key)
    job.save(update_fields=['total_rows'])
    return job


def process_import_chunk(job, chunk_size=100, user=None):
    if job.status == 'DONE':
        return job

    job.status = 'RUNNING'
    job.save(update_fields=['status'])

    wb = load_workbook(job.upload.path, read_only=True, data_only=True)
    ws = select_sheet(wb, job.model_key)
    headers = [clean_value(c.value) for c in next(ws.iter_rows(min_row=1, max_row=1))]
    normalized_headers = [_sheet_header(h, job.model_key) for h in headers]
    field_map = HEADER_MAPS[job.model_key]
    processed_this_call = 0
    seen_data_rows = 0
    current_controller_serial = ''

    for values in ws.iter_rows(min_row=2, values_only=True):
        if not any(clean_value(v) for v in values):
            continue
        seen_data_rows += 1

        # Match sheet columns to the header map ignoring case/spacing — the
        # same real-world files spell "QTY" as "Qty" and "Part No" as "Part no".
        raw = dict(zip(normalized_headers, values))
        row = {target: clean_value(raw.get(_normalize_header(source))) for source, target in field_map.items()}
        row['qty'] = normalize_qty(row.get('qty'))
        row['store_location'] = job.store_location or DEFAULT_STORE
        if job.model_key == 'stock_out':
            row['stock_status'] = row.get('stock_status') or 'SALE'
            row['stock_out_date'] = row.get('stock_out_date') or date.today().isoformat()
        else:
            # Optional "Stock In Status" column: if present and a recognized
            # status (e.g. FAULTY, DAMAGED), stock the row in with that
            # status instead of the default LIVE. It still counts as "in
            # stock" — only a Stock Out transaction removes it from the
            # active list. Combined Stock-In + Stock-Out imports also read
            # this for the stock-in leg (the appended "Stock Status" column
            # is separate and only drives the stock-out leg).
            provided_status = (row.get('stock_status') or '').strip().upper()
            row['stock_status'] = provided_status if provided_status in VALID_STOCK_STATUSES else DEFAULT_STATUS

        if job.model_key == 'controller':
            spare_type = (row.get('spare_type') or '').strip().upper()
            serial = (row.get('serial_no') or '').strip().upper()
            parent_serial = (row.get('parent_child_location') or '').strip().upper()

            if spare_type == 'CONTROLLER' and serial:
                current_controller_serial = serial
            elif not parent_serial and current_controller_serial:
                row['parent_child_location'] = current_controller_serial

        if seen_data_rows <= job.processed_rows:
            continue
        if processed_this_call >= chunk_size:
            break

        try:
            with transaction.atomic():
                product = import_row(job.model_key, row, user=user)
                if getattr(product, '_import_updated', False):
                    job.updated_count += 1
                else:
                    mark_latest_stock_user(product, user)
            job.success_count += 1
        except Exception as exc:
            job.error_count += 1
            errors = list(job.errors or [])
            errors.append({'row': seen_data_rows + 1, 'error': str(exc)})
            job.errors = errors[-1000:]

        job.processed_rows += 1
        processed_this_call += 1

    just_finished = job.processed_rows >= job.total_rows
    if just_finished:
        job.status = 'DONE'

    job.save(update_fields=[
        'processed_rows', 'success_count', 'updated_count', 'error_count', 'errors', 'status', 'updated_at'
    ])
    if just_finished and job.error_count:
        _notify_import_failure(job)
    return job


def _notify_import_failure(job, reason=None):
    """Mail the failure reason to the alert recipients; never raises."""
    try:
        from apps.core.notifications import send_import_failure_email
        send_import_failure_email(job, reason)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Import failure email failed for job %s', job.pk)


def mark_latest_stock_user(product, user):
    if not product or not getattr(user, 'is_authenticated', False):
        return
    txn = InventoryTransaction.objects.filter(product=product, transaction_type='IN').order_by('-created_at').first()
    if txn:
        txn.performed_by = user
        txn.save(update_fields=['performed_by'])
        log_activity(
            action='IMPORT_STOCK_IN',
            module='IMPORT',
            entity=product.name,
            entity_id=product.id,
            user=user,
            barcode='',
            warehouse=txn.store_location,
            location='',
            new_values={
                'transaction_id': txn.id,
                'model': product.model,
                'stock_status': txn.stock_status,
            },
            remarks='Imported stock in',
        )
        log_timeline(
            product=product,
            event_type='IMPORT',
            user=user,
            warehouse=txn.store_location,
            details={
                'transaction_type': 'IN',
                'stock_status': txn.stock_status,
            },
        )


def import_row(model_key, row, user=None):
    # Stock-in imports: a barcode that is already in the system updates that
    # item instead of failing as a duplicate (see update_existing_from_row).
    if model_key != 'stock_out' and not model_key.endswith('_stock_out'):
        existing = existing_product_by_barcode(row.get('barcode'))
        if existing is not None:
            existing._import_changes = update_existing_from_row(existing, row, model_key)
            existing._import_updated = True
            if model_key == 'server' or model_key in SERVER_GROUP_IMPORTS:
                _update_server_fields(row)
            elif model_key == 'controller' and not _is_controller_parent_row(row):
                # A component row may also (re)attach the item to the parent controller.
                import_controller_row(row, user=user)
            return existing
    if model_key == 'networking_spare':
        return create_product_and_networking_spare(row, user=user)
    if model_key == 'controller':
        return import_controller_row(row, user=user)
    if model_key == 'server':
        return import_server_row(row, user=user)
    if model_key in SERVER_GROUP_IMPORTS:
        return import_server_row(row, user=user, group=SERVER_GROUP_IMPORTS[model_key])
    if model_key == 'stock_out':
        return import_stock_out_row(row, user=user)
    if model_key.endswith('_stock_out'):
        base_key = model_key[:-len('_stock_out')]
        return import_combined_stock_out_row(base_key, row, user=user)
    creator = CREATE_BY_KEY[model_key]
    return creator(row)


# Appended Stock Out columns (see STOCK_OUT_APPEND_COLUMNS) — a row is only
# stocked out when at least one of these carries a value; otherwise the row is
# stocked in only.
STOCK_OUT_DETAIL_FIELDS = (
    'so_client_name', 'so_invoice_no', 'so_olf_dc_number',
    'so_stock_status', 'so_stock_out_date',
)


def _row_has_stock_out_details(row):
    return any((row.get(field) or '').strip() for field in STOCK_OUT_DETAIL_FIELDS)


def import_combined_stock_out_row(base_key, row, user=None):
    """Stock in every row; stock out only rows that actually carry Stock Out
    details (Client / Invoice / OLF-DC / Stock Status / Stock Out Date).

    So in a 10-row file where only 2 rows have stock-out columns filled, those
    2 are stocked out and the other 8 are stocked in only.
    """
    if base_key not in HEADER_MAPS:
        raise ValueError(f'Unknown stock-out base model: {base_key}')

    try:
        product = _product_from_stock_out_row(row)
    except ValueError:
        product = import_row(base_key, row, user=user)
    else:
        # Already in the system: refresh its details from the row, then stock it out.
        update_existing_from_row(product, row, base_key)

    # No stock-out details on this row → stock in only.
    if not _row_has_stock_out_details(row):
        return product

    so_row = {
        'serial_no': product.serial_no or '',
        'barcode': '',
        'client_name': row.get('so_client_name') or '',
        'invoice_no': row.get('so_invoice_no') or '',
        'olf_dc_number': row.get('so_olf_dc_number') or '',
        'stock_status': row.get('so_stock_status') or 'SALE',
        'stock_out_date': row.get('so_stock_out_date') or '',
        # Carry the import's selected warehouse through to the stock-out side too.
        'store_location': row.get('store_location') or '',
    }
    _apply_stock_out(product, so_row, user=user)
    return product


def _product_from_stock_out_row(row):
    from apps.categories.models import (
        Card, Controller, CPU, HardDisk, Memory, NetworkingSpare, RailKit, SFP, Spare,
    )
    from apps.servers.models import Server, ServerComponent

    serial = (row.get('serial_no') or '').strip().upper()
    barcode = (row.get('barcode') or '').strip().upper()

    if serial:
        product = Product.objects.filter(serial_no=serial).first()
        if product:
            return product

    if barcode:
        related_models = (
            Spare, Card, CPU, Memory, SFP, RailKit, HardDisk, NetworkingSpare,
            Controller, Server, ServerComponent,
        )
        for model in related_models:
            item = model.objects.filter(barcode__iexact=barcode).select_related('product').first()
            if item:
                return item.product
        # Hard disks can also be identified by their tray barcode.
        item = HardDisk.objects.filter(tray_barcode__iexact=barcode).select_related('product').first()
        if item:
            return item.product

    raise ValueError('Product not found by Serial No or Barcode No')


_STOCK_OUT_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y', '%d/%m/%y', '%d-%m-%y')


def _parse_stock_out_date(value):
    text = str(value or '').strip()
    if not text:
        return ''
    for fmt in _STOCK_OUT_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f'Invalid Stock Out Date "{text}" (use DD/MM/YYYY or YYYY-MM-DD)')


def import_stock_out_row(row, user=None):
    """Common "Stock Out" import: one row = one barcode.

    Only Barcode No, Client Name, Invoice No, OLF / DC No, Stock Status and
    Stock Out Date are read. The product is found by barcode in ANY category
    (spares, cards, CPUs, memory, SFP, rail kits, hard disks, networking,
    controllers, servers and server components). An unknown barcode raises an
    error naming that barcode, and the import carries on with the next row."""
    from apps.inventory.views import _has_pending_transfer, _is_frozen

    barcode = (row.get('barcode') or '').strip()
    if not barcode:
        raise ValueError('Barcode No is empty')
    try:
        product = _product_from_stock_out_row({'barcode': barcode})
    except ValueError:
        raise ValueError(f'Barcode "{barcode}" not found in inventory')

    latest = product.transactions.order_by('-created_at', '-id').first()
    if latest and latest.transaction_type == 'OUT':
        raise ValueError(f'Barcode "{barcode}" is already stocked out')
    if _is_frozen(product):
        raise ValueError(f'Barcode "{barcode}" is frozen and cannot be stocked out')
    if _has_pending_transfer(product):
        raise ValueError(f'Barcode "{barcode}" is pending receipt in a transfer request')

    so_row = dict(row)
    so_row['stock_out_date'] = _parse_stock_out_date(row.get('stock_out_date'))
    return _apply_stock_out(product, so_row, user=user)


def _apply_stock_out(product, row, user=None):
    """Stock out an already-resolved product using a stock-out row dict.

    Shared by the standalone Stock Out import and the per-category combined
    Stock In + Stock Out import. Validates the stock status and date, cascades
    to server components, and writes activity + timeline entries."""
    from datetime import date

    from apps.inventory.views import (
        _create_stock_out_transaction,
        _latest_location,
        _latest_store_location,
        _stock_out_server_components,
        create_rental_record,
    )

    raw_status = (row.get('stock_status') or 'SALE').strip()
    stock_status = normalize_stock_status(raw_status)
    if not stock_status:
        raise ValueError(f'Invalid stock status: {raw_status}')

    raw_date = row.get('stock_out_date')
    stock_out_date = date.today()
    if raw_date:
        try:
            stock_out_date = datetime.strptime(str(raw_date), '%Y-%m-%d').date()
        except ValueError:
            stock_out_date = date.today()

    # Use the import's selected warehouse when one was provided (dropdown on
    # the import page); otherwise fall back to the product's current warehouse
    # (e.g. the standalone "Stock Out" import for pre-existing products).
    valid_locations = dict(InventoryTransaction.STORE_LOCATION)
    row_store_location = (row.get('store_location') or '').strip().upper()
    store_location = row_store_location if row_store_location in valid_locations else _latest_store_location(product)
    client_name = row.get('client_name') or ''
    invoice_no = row.get('invoice_no') or ''
    olf_dc_number = row.get('olf_dc_number') or ''
    if stock_status in NAME_ONLY_STOCK_OUT:
        # In-house use / return to vendor: the Client column holds the employee / vendor.
        invoice_no = olf_dc_number = ''
        if not client_name.strip():
            who = 'employee (in the Client column)' if stock_status == 'IN_HOUSE' else 'vendor (in the Client column)'
            raise ValueError(f'{dict(InventoryTransaction.STOCK_STATUS)[stock_status]} needs the {who}')

    with transaction.atomic():
        _create_stock_out_transaction(
            product=product,
            store_location=store_location,
            stock_status=stock_status,
            stock_out_date=stock_out_date,
            client_name=client_name,
            invoice_no=invoice_no,
            user=user,
            olf_dc_number=olf_dc_number,
        )
        affected = _stock_out_server_components(
            product=product,
            store_location=store_location,
            stock_status=stock_status,
            stock_out_date=stock_out_date,
            client_name=client_name,
            invoice_no=invoice_no,
            user=user,
            olf_dc_number=olf_dc_number,
        )

        if stock_status == 'RENT':
            create_rental_record(
                product=product,
                store_location=store_location,
                stock_out_date=stock_out_date,
                client_name=client_name,
                invoice_no=invoice_no,
                olf_dc_number=olf_dc_number,
                user=user,
                remarks='Rented out (import)',
            )

    log_activity(
        action='IMPORT_STOCK_OUT',
        module='IMPORT',
        entity=product.name,
        entity_id=product.id,
        user=user,
        warehouse=store_location,
        location=_latest_location(product),
        new_values={
            'stock_status': stock_status,
            'stock_out_date': str(stock_out_date),
            'client_name': client_name,
            'invoice_no': invoice_no,
            'olf_dc_number': olf_dc_number,
            'components_stocked_out': affected,
        },
        remarks='Stock-out imported from Excel',
    )
    log_timeline(
        product=product,
        event_type='OUT',
        user=user,
        warehouse=store_location,
        location=_latest_location(product),
        remarks='Stock-out imported from Excel',
        details={'invoice_no': invoice_no, 'olf_dc_number': olf_dc_number, 'stock_status': stock_status},
    )
    return product


def create_product_and_networking_spare(data, user=None):
    category_name = (data.get('category') or 'NETWORKING SPARE').strip().upper()
    category, _ = SpareCategory.objects.get_or_create(name=category_name)
    brand_name = (data.get('brand') or '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    product = Product.objects.create(
        category=category,
        serial_no=(data.get('serial_no') or '').strip().upper(),
        part_no=data.get('part_no'),
        brand=brand_name,
        model=category_name,
        name=f"{category_name} - {brand_name} - {data.get('part_no', '')}".strip(' -'),
    )
    NetworkingSpare.objects.create(
        product=product,
        brand=brand,
        part_no=data.get('part_no'),
        alt_part_no=data.get('alt_part_no'),
        alt_serial_no=data.get('alt_serial_no'),
        specs=data.get('specs'),
        qty=data.get('qty') or 1,
        barcode=data.get('barcode') or None,
        location=data.get('location'),
        reference_location=data.get('reference_location'),
        remark=data.get('remark'),
    )
    from apps.core.services import _create_stock_in_transaction
    _create_stock_in_transaction(
        product=product,
        store_location=data.get('store_location') or DEFAULT_STORE,
        stock_status=data.get('stock_status') or DEFAULT_STATUS,
        user=user,
        remarks='Networking spare import stock-in',
    )
    return product


def _is_controller_parent_row(row):
    spare_type = (row.get('spare_type') or row.get('product_category') or '').strip().upper()
    product_name = (row.get('product_name') or row.get('product_type') or '').strip().upper()
    return spare_type == 'CONTROLLER' or product_name == 'CABINET'


def import_controller_row(row, user=None):
    from apps.categories.models import Controller, Spare
    from apps.core.services import create_controller_with_components

    spare_type = (row.get('spare_type') or row.get('product_category') or '').strip().upper()
    product_name = (row.get('product_name') or row.get('product_type') or '').strip()
    serial = (row.get('serial_no') or '').strip().upper()
    barcode = (row.get('barcode') or '').strip().upper()
    parent_serial = (row.get('parent_child_location') or '').strip().upper()

    if spare_type == 'CONTROLLER' or product_name.upper() == 'CABINET':
        existing = Controller.objects.filter(product__serial_no=serial).select_related('product').first()
        if existing:
            return existing.product

        controller_data = dict(row)
        controller_data['model'] = row.get('model') or 'CONTROLLER'
        controller_data['serial_no'] = serial
        controller_data['spare_type'] = 'CONTROLLER'
        controller_data['product_name'] = product_name or 'CONTROLLER'
        controller = create_controller_with_components(controller_data, [])
        mark_latest_stock_user(controller.product, user)
        return controller.product

    if not parent_serial:
        raise ValueError('Parent-child Location must contain parent controller serial for controller components')

    controller = Controller.objects.filter(
        Q(product__serial_no=parent_serial) | Q(alt_serial_no=parent_serial)
    ).select_related('product').first()
    if not controller:
        raise ValueError(f'Parent controller not found for parent serial: {parent_serial}')

    existing_product = None
    if serial:
        existing_product = Product.objects.filter(serial_no=serial).first()
    elif barcode:
        existing_spare = Spare.objects.select_related('product').filter(barcode__iexact=barcode).first()
        if existing_spare:
            existing_product = existing_spare.product

    if existing_product:
        existing_component = Spare.objects.filter(
            controller=controller,
            product=existing_product,
        ).first()
        if existing_component:
            return existing_product

        orphan_controller = getattr(existing_product, 'controller', None)
        if orphan_controller and orphan_controller.pk != controller.pk and orphan_controller.components.count() == 0:
            orphan_controller.delete()

        brand_name = (row.get('brand') or '').strip().upper()
        brand = None
        if brand_name:
            brand, _ = Brand.objects.get_or_create(name=brand_name)

        category_name = spare_type or 'SPARE'
        category, _ = SpareCategory.objects.get_or_create(name=category_name)
        existing_product.category = category
        existing_product.part_no = row.get('part_no')
        existing_product.brand = brand_name
        existing_product.model = row.get('model')
        existing_product.name = (
            product_name
            or f"CONTROLLER - {category_name} - {row.get('model', '')} - {brand_name}".strip(' -')
        )
        existing_product.save(update_fields=['category', 'part_no', 'brand', 'model', 'name'])

        spare_record = getattr(existing_product, 'spare', None)
        if spare_record:
            spare_record.controller = controller
            spare_record.brand = brand
            spare_record.model = row.get('model')
            spare_record.part_no = row.get('part_no')
            spare_record.alt_part_no = row.get('alt_part_no')
            spare_record.alt_serial_no = row.get('alt_serial_no')
            spare_record.specs = row.get('specs')
            spare_record.qty = row.get('qty') or 1
            spare_record.barcode = barcode or None
            spare_record.location = spare_record.location or row.get('location') or controller.location  # never moved by an import
            spare_record.reference_location = spare_record.reference_location or row.get('reference_location') or controller.reference_location
            spare_record.remark = row.get('remark')
            spare_record.save()
        else:
            Spare.objects.create(
                product=existing_product,
                controller=controller,
                brand=brand,
                model=row.get('model'),
                part_no=row.get('part_no'),
                alt_part_no=row.get('alt_part_no'),
                alt_serial_no=row.get('alt_serial_no'),
                specs=row.get('specs'),
                qty=row.get('qty') or 1,
                barcode=barcode or None,
                location=row.get('location') or controller.location,
                reference_location=row.get('reference_location') or controller.reference_location,
                remark=row.get('remark'),
            )
        return existing_product

    category_name = spare_type or 'SPARE'
    category, _ = SpareCategory.objects.get_or_create(name=category_name)

    brand_name = (row.get('brand') or '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    product = Product.objects.create(
        category=category,
        serial_no=serial,
        part_no=row.get('part_no'),
        brand=brand_name,
        model=row.get('model'),
        name=product_name or f"CONTROLLER - {category_name} - {row.get('model', '')} - {brand_name}".strip(' -'),
    )

    Spare.objects.create(
        product=product,
        controller=controller,
        brand=brand,
        model=row.get('model'),
        part_no=row.get('part_no'),
        alt_part_no=row.get('alt_part_no'),
        alt_serial_no=row.get('alt_serial_no'),
        specs=row.get('specs'),
        qty=row.get('qty') or 1,
        barcode=barcode or None,
        location=row.get('location') or controller.location,
        reference_location=row.get('reference_location') or controller.reference_location,
        remark=row.get('remark'),
    )

    last_controller_txn = InventoryTransaction.objects.filter(
        product=controller.product
    ).order_by('-created_at').first()

    from apps.core.services import _create_stock_in_transaction
    fallback_store = (row.get('store_location') or DEFAULT_STORE).strip().upper()
    # A component's status normally inherits from its parent controller's
    # current status, but an explicit "Stock In Status" column on the
    # component row (e.g. FAULTY, DAMAGED) overrides that.
    provided_component_status = (row.get('stock_status') or '').strip().upper()
    if provided_component_status in VALID_STOCK_STATUSES:
        component_status = provided_component_status
    else:
        component_status = last_controller_txn.stock_status if last_controller_txn else DEFAULT_STATUS
    _create_stock_in_transaction(
        product=product,
        store_location=last_controller_txn.store_location if last_controller_txn else fallback_store,
        stock_status=component_status,
        user=user,
        remarks='Controller component import stock-in',
    )

    return product


def import_server_row(row, user=None, group=None):
    """One sheet row of a server import. ``group`` comes from a group-specific
    import option; the generic Server import leaves it None and the group is
    inferred from Machine Type / Model when the server is first created."""
    service_tag = (row.get('service_tag') or '').strip().upper()
    service_tag_missing = False
    if not service_tag:
        # No tag in the sheet: still store the machine, grouping its rows by
        # Machine no under a placeholder tag, and flag it so the lists show
        # "System Service Tag No is missing" on hover.
        machine_no = ' '.join((row.get('machine_no') or '').upper().split())
        if not machine_no:
            raise ValueError('System Service Tag No and Machine no are both missing — cannot tell which machine this row belongs to')
        service_tag = f'NOTAG-{machine_no}'
        service_tag_missing = True

    store_location = (row.get('store_location') or DEFAULT_STORE).strip().upper()
    provided_status = (row.get('stock_status') or '').strip().upper()
    stock_status = provided_status if provided_status in VALID_STOCK_STATUSES else DEFAULT_STATUS

    server_data = {
        'testing_date': row.get('testing_date'),
        'tested_by': row.get('tested_by'),
        'machine_type': row.get('machine_type'),
        'machine_no': row.get('machine_no'),
        'group': group or '',
        'service_tag': service_tag,
        'service_tag_missing': service_tag_missing,
        'model': row.get('server_model'),
        'brand': '',
        'part_no': '',
        'alt_part_no': '',
        'alt_serial_no': '',
        'specs': '',
        'qty': 1,
        'barcode': '',
        'status': 'WORKING',
        'location': row.get('location'),
        'reference_location': row.get('reference_location'),
        'parent_child_location': row.get('parent_child_location'),
        'remark': row.get('remark'),
        'store_location': store_location,
        'stock_status': stock_status,
    }
    component = {
        'spare_type': row.get('spare_type'),
        'brand': '',
        'model': row.get('server_model'),
        'part_no': row.get('part_no'),
        'alt_part_no': row.get('alt_part_no'),
        'serial_no': row.get('serial_no'),
        'alt_serial_no': row.get('alt_serial_no'),
        'specs': row.get('specs'),
        'barcode': row.get('barcode'),
        'qty': row.get('qty') or 1,
        'working_status': row.get('working_status') or 'WORKING',
        'location': row.get('location'),
        'reference_location': row.get('reference_location'),
        'parent_child_location': row.get('parent_child_location'),
        'remark': row.get('remark'),
    }

    server = Server.objects.filter(service_tag=service_tag).first()
    if not server:
        server = create_server_with_components(server_data, [component])
        mark_latest_stock_user(server.product, user)
    else:
        product = add_server_component(server, component, store_location, stock_status).product
        mark_latest_stock_user(product, user)
    return server.product
