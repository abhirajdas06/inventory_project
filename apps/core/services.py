from apps.core.models import Product, SpareCategory, Brand
from apps.categories.models import Card, Spare
from datetime import date
from apps.inventory.models import InventoryTransaction
from apps.core.activity import log_activity, log_timeline

from datetime import date as _date


def _create_stock_in_transaction(product, store_location='WH1', stock_status='LIVE', user=None, remarks=''):
    txn = InventoryTransaction.objects.create(
        product=product,
        transaction_type='IN',
        store_location=store_location or 'WH1',
        stock_status=stock_status or 'LIVE',
        stock_in_date=date.today(),
        performed_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    log_activity(
        action='STOCK_IN',
        module='INVENTORY',
        entity=product.name,
        entity_id=product.id,
        user=user,
        warehouse=txn.store_location,
        new_values={
            'transaction_id': txn.id,
            'stock_status': txn.stock_status,
        },
        remarks=remarks or 'Stock in created',
    )
    log_timeline(
        product=product,
        event_type='IN',
        user=user,
        warehouse=txn.store_location,
        remarks=remarks,
        details={'stock_status': txn.stock_status},
    )
    return txn


def create_product_and_spare(data):
    _validate_barcode(data.get('barcode'))
    # 🔹 CATEGORY
    category_name = data.get('category', '').strip().upper()
    category, _ = SpareCategory.objects.get_or_create(name=category_name)

    # 🔹 BRAND
    brand_name = data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    # 🔹 NAME
    name = f"{category_name} - {data.get('model', '')} - {brand_name}"

    # 🔹 CREATE PRODUCT
    product = Product.objects.create(
        category=category,
        serial_no=data.get('serial_no'),
        part_no=data.get('part_no'),
        brand=brand_name,
        model=data.get('model'),
        name=name
    )

    # 🔹 CREATE SPARE (GENERIC TABLE)
    Spare.objects.create(
        product=product,
        brand=brand,
        model=data.get('model'),
        part_no=data.get('part_no'),
        alt_part_no=data.get('alt_part_no'),
        alt_serial_no=data.get('alt_serial_no'),
        specs=data.get('specs'),
        qty=data.get('qty') or 1,
        barcode=data.get('barcode'),
        location=data.get('location'),
        reference_location=data.get('reference_location'),
        remark=data.get('remark')
    )

    # 🔥 AUTO STOCK IN (CORE LOGIC)
    store_location = data.get('store_location') or 'WH1'
    stock_status = data.get('stock_status') or 'LIVE'

    _create_stock_in_transaction(
        product=product,
        store_location=store_location,
        stock_status=stock_status,
        remarks='Spare stock in',
    )

    # 🔥 UPDATE CURRENT STATE (IMPORTANT)
    product.current_location = store_location
    product.current_status = stock_status
    product.save()

    return product


def create_product_and_card(data):
    _validate_barcode(data.get('barcode'))
    category, _ = SpareCategory.objects.get_or_create(name="CARD")

    brand_name = data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    name = f"CARD - {data.get('brand_model_no')} - {brand_name}"

    product = Product.objects.create(
        category=category,
        serial_no=data.get('brand_serial_no_1'),
        part_no=data.get('part_no'),
        brand=brand,
        model=data.get('brand_model_no'),
        name=name
    )

    Card.objects.create(
        product=product,
        brand=brand,
        oem=data.get('oem'),
        brand_model_no=data.get('brand_model_no'),
        interface=data.get('interface'),
        part_no=data.get('part_no'),
        alt_part_no=data.get('alt_part_no'),
        brand_serial_no_1=data.get('brand_serial_no_1'),
        capacity=data.get('capacity'),
        port=data.get('port'),
        barcode=data.get('barcode'),
        location=data.get('location'),
        reference_location=data.get('reference_location'),
        remark=data.get('remark')
    )

    # 🔥 AUTO STOCK IN
    _create_stock_in_transaction(
        product=product,
        store_location=data.get('store_location') or 'WH1',
        stock_status=data.get('stock_status') or 'LIVE',
        remarks='Card stock in',
    )

    return product


def create_product_and_cpu(data):
    from apps.categories.models import CPU

    _validate_barcode(data.get('barcode'))
    category, _ = SpareCategory.objects.get_or_create(name="PROCESSOR")

    brand_name = data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    name = f"PROCESSOR - {data.get('model', '')} - {brand_name}"

    product = Product.objects.create(
        category=category,
        serial_no=data.get('part_no'),
        part_no=data.get('part_no'),
        brand=brand,
        model=data.get('model'),
        name=name
    )

    CPU.objects.create(
        product=product,
        brand=brand,
        model=data.get('model'),
        part_no=data.get('part_no'),
        no_of_cores=data.get('no_of_cores'),
        no_of_threads=data.get('no_of_threads'),
        ghz=data.get('ghz'),
        frequency=data.get('frequency'),
        cache=data.get('cache'),
        barcode=data.get('barcode'),
        location=data.get('location'),
        reference_location=data.get('reference_location'),
        remark=data.get('remark')
    )

    # AUTO STOCK IN
    _create_stock_in_transaction(
        product=product,
        store_location=data.get('store_location') or 'WH1',
        stock_status=data.get('stock_status') or 'LIVE',
        remarks='CPU stock in',
    )

    return product



def create_controller_with_components(controller_data, components):
    """
    controller_data  : dict with fields for the parent Controller
    components    : list of dicts, each is a spare component row
    
    Flow:
      1. Create Product for controller
      2. Create Controller record
      3. Auto stock IN for controller
      4. For each component → create Product + Spare (linked to controller) + stock IN
    """
    from apps.categories.models import Controller, Spare
    _validate_barcode(controller_data.get('barcode'))
    controller_category, _ = SpareCategory.objects.get_or_create(name='CONTROLLER')
 
    brand_name = controller_data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)
 
    controller_name = (
        controller_data.get('product_name')
        or f"CONTROLLER - {controller_data.get('model', '')} - {brand_name}".strip(' -')
    )
 
    cabinet_product = Product.objects.create(
        category=controller_category,
        serial_no=controller_data.get('serial_no'),
        part_no=controller_data.get('part_no'),
        brand=brand,
        model=controller_data.get('model'),
        name=controller_name
    )
 
    # --- CONTROLLER RECORD ---
    controller = Controller.objects.create(
        product=cabinet_product,
        brand=brand,
        model=controller_data.get('model'),
        part_no=controller_data.get('part_no'),
        alt_part_no=controller_data.get('alt_part_no'),
        alt_serial_no=controller_data.get('alt_serial_no'),
        specs=controller_data.get('specs'),
        qty=controller_data.get('qty') or 1,
        barcode=controller_data.get('barcode'),
        location=controller_data.get('location'),
        reference_location=controller_data.get('reference_location'),
        parent_child_location=controller_data.get('parent_child_location'),
        remark=controller_data.get('remark')
    )
 
    _create_stock_in_transaction(
        product=cabinet_product,
        store_location=controller_data.get('store_location') or 'WH1',
        stock_status=controller_data.get('stock_status') or 'LIVE',
        remarks='Controller stock in',
    )
 
    # --- COMPONENTS ---
    for comp in components:
        _validate_barcode(comp.get('barcode'))      # ← each component

        if not comp.get('serial_no', '').strip():
            continue
 
        comp_category_name = (
            comp.get('spare_type')
            or comp.get('product_category')
            or ''
        ).strip().upper()
        comp_category, _ = SpareCategory.objects.get_or_create(name=comp_category_name)
 
        comp_brand_name = comp.get('brand', '').strip().upper()
        comp_brand = None
        if comp_brand_name:
            comp_brand, _ = Brand.objects.get_or_create(name=comp_brand_name)
 
        comp_name = (
            comp.get('product_name')
            or f"CONTROLLER - {comp_category_name} - {comp.get('model', '')} - {comp_brand_name}".strip(' -')
        )
 
        comp_product = Product.objects.create(
            category=comp_category,
            serial_no=comp.get('serial_no').strip().upper(),
            part_no=comp.get('part_no'),
            brand=comp_brand,
            model=comp.get('model'),
            name=comp_name
        )
 
        # Create Spare entry — linked to controller
        Spare.objects.create(
            product=comp_product,
            controller=controller,          # KEY LINK
            brand=comp_brand,
            model=comp.get('model'),
            part_no=comp.get('part_no'),
            alt_part_no=comp.get('alt_part_no'),
            alt_serial_no=comp.get('alt_serial_no'),
            specs=comp.get('specs'),
            qty=comp.get('qty') or 1,
            barcode=comp.get('barcode'),
            location=controller_data.get('location'),
            reference_location=controller_data.get('reference_location'),
            remark=comp.get('remark')
        )
 
        # Auto stock IN for component
        _create_stock_in_transaction(
            product=comp_product,
            store_location=controller_data.get('store_location') or 'WH1',
            stock_status=controller_data.get('stock_status') or 'LIVE',
            remarks='Controller component stock in',
        )
 
    return controller

def create_product_and_memory(data):
    from apps.categories.models import Memory
    _validate_barcode(data.get('barcode'))
    category, _ = SpareCategory.objects.get_or_create(name='MEMORY')
 
    brand_name = data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)
 
    size        = data.get('size', '')
    ddr_version = data.get('ddr_version', '')
    oem         = data.get('oem', '')
    name = f"MEMORY - {size} {ddr_version} - {brand_name} ({oem})"
 
    product = Product.objects.create(
        category  = category,
        serial_no = data.get('serial_no', '').strip().upper(),
        part_no   = data.get('part_no_1'),
        brand     = brand,
        model     = data.get('model'),
        name      = name
    )
 
    Memory.objects.create(
        product    = product,
        brand      = brand,
        oem        = data.get('oem'),
        model      = data.get('model'),
        part_no_1  = data.get('part_no_1'),
        part_no_2  = data.get('part_no_2'),
        part_no_3  = data.get('part_no_3'),
        size       = data.get('size'),
        ram_type   = data.get('ram_type'),
        ddr_version= data.get('ddr_version'),
        frequency  = data.get('frequency'),
        rank       = data.get('rank'),
        qty        = data.get('qty') or 1,
        barcode    = data.get('barcode'),
        location           = data.get('location'),
        reference_location = data.get('reference_location'),
        remark             = data.get('remark'),
    )
 
    # AUTO STOCK IN
    _create_stock_in_transaction(
        product=product,
        store_location=data.get('store_location') or 'WH1',
        stock_status=data.get('stock_status') or 'LIVE',
        remarks='Memory stock in',
    )
 
    return product

def create_product_and_sfp(data):
    from apps.categories.models import SFP
 
    _validate_barcode(data.get('barcode'))
    category, _ = SpareCategory.objects.get_or_create(name='SFP')
 
    brand_name = data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)
 
    model     = data.get('model', '')
    data_rate = data.get('data_rate', '')
    name = f"SFP - {model} - {data_rate} - {brand_name}".strip(' -')
 
    product = Product.objects.create(
        category  = category,
        serial_no = data.get('serial_no', '').strip().upper(),
        part_no   = data.get('part_no'),
        brand     = brand,
        model     = model,
        name      = name
    )
 
    SFP.objects.create(
        product     = product,
        brand       = brand,
        model       = model,
        part_no     = data.get('part_no'),
        description = data.get('description'),
        fibre_type  = data.get('fibre_type'),
        data_rate   = data.get('data_rate'),
        barcode            = data.get('barcode'),
        location           = data.get('location'),
        reference_location = data.get('reference_location'),
        remark             = data.get('remark'),
    )
 
    # AUTO STOCK IN
    _create_stock_in_transaction(
        product=product,
        store_location=data.get('store_location') or 'WH1',
        stock_status=data.get('stock_status') or 'LIVE',
        remarks='SFP stock in',
    )
 
    return product


def create_product_and_railkit(data):
    from apps.categories.models import RailKit
 
    category, _ = SpareCategory.objects.get_or_create(name='RAILKIT')
    _validate_barcode(data.get('barcode'))
 
    brand_name = data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)
 
    side            = data.get('side', '')
    supported_model = data.get('supported_model', '')
    name = f"RAILKIT - {brand_name} - {side} - {supported_model}".strip(' -')
 
    product = Product.objects.create(
        category  = category,
        serial_no = data.get('serial_no', '').strip().upper(),
        part_no   = data.get('part_no'),
        brand     = brand,
        model     = supported_model,
        name      = name
    )
 
    RailKit.objects.create(
        product         = product,
        brand           = brand,
        side            = side,
        part_no         = data.get('part_no'),
        specs           = data.get('specs'),
        supported_model = supported_model,
        qty             = data.get('qty') or 1,
        barcode         = data.get('barcode'),
        location           = data.get('location'),
        reference_location = data.get('reference_location'),
        remark             = data.get('remark'),
    )
 
    # AUTO STOCK IN
    _create_stock_in_transaction(
        product=product,
        store_location=data.get('store_location') or 'WH1',
        stock_status=data.get('stock_status') or 'LIVE',
        remarks='Rail kit stock in',
    )
 
    return product


def create_product_and_harddisk(data):
    from apps.categories.models import HardDisk
 
    category, _ = SpareCategory.objects.get_or_create(name='HARD DISK')
    _validate_barcode(data.get('barcode'))
    brand_name = data.get('brand', '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)
 
    capacity  = data.get('capacity', '')
    interface = data.get('interface', '')
    size      = data.get('size', '')
    oem       = data.get('oem', '')
 
    name = (
        f"HDD - {capacity} {interface} {size} - {brand_name} ({oem})"
        .strip()
        .strip('()')
        .replace('  ', ' ')
    )
 
    product = Product.objects.create(
        category  = category,
        serial_no = data.get('serial_no', '').strip().upper(),
        part_no   = data.get('part_no'),
        brand     = brand,
        model     = data.get('oem_model_no') or data.get('brand_model_no'),
        name      = name
    )
 
    HardDisk.objects.create(
        product        = product,
        brand          = brand,
        oem            = data.get('oem'),
        brand_model_no = data.get('brand_model_no'),
        oem_model_no   = data.get('oem_model_no'),
        capacity       = capacity,
        rpm            = data.get('rpm'),
        interface      = data.get('interface'),
        size           = data.get('size'),
        part_no        = data.get('part_no'),
        alt_part_no    = data.get('alt_part_no'),
        alt_fru_1      = data.get('alt_fru_1'),
        alt_fru_2      = data.get('alt_fru_2'),
        alt_fru_3      = data.get('alt_fru_3'),
        retail_part_no = data.get('retail_part_no'),
        spare_part_tray= data.get('spare_part_tray'),
        gpn_code       = data.get('gpn_code'),
        brand_serial_no= data.get('brand_serial_no'),
        oem_serial_no  = data.get('oem_serial_no'),
        firmware       = data.get('firmware'),
        health         = data.get('health'),
        gb_s           = data.get('gb_s'),
        barcode        = data.get('barcode'),
        tray_barcode   = data.get('tray_barcode'),
        location           = data.get('location'),
        reference_location = data.get('reference_location'),
        remark             = data.get('remark'),
    )
 
    # AUTO STOCK IN
    _create_stock_in_transaction(
        product=product,
        store_location=data.get('store_location') or 'WH1',
        stock_status=data.get('stock_status') or 'LIVE',
        remarks='Hard disk stock in',
    )
 
    return product



def _validate_barcode(barcode, exclude_tray=False):
    """Raise ValueError if barcode already exists anywhere."""
    from apps.categories.models import (
        Spare, Card, CPU, Memory, SFP, RailKit, HardDisk, Controller
    )
    if not barcode:
        return  # barcode is optional — skip if blank
 
    barcode = barcode.strip().upper()
 
    exists = (
        Spare.objects.filter(barcode=barcode).exists()          or
        Card.objects.filter(barcode=barcode).exists()           or
        CPU.objects.filter(barcode=barcode).exists()            or
        Memory.objects.filter(barcode=barcode).exists()         or
        SFP.objects.filter(barcode=barcode).exists()            or
        RailKit.objects.filter(barcode=barcode).exists()        or
        HardDisk.objects.filter(barcode=barcode).exists()       or
        HardDisk.objects.filter(tray_barcode=barcode).exists()  or
        Controller.objects.filter(barcode=barcode).exists()
    )
 
    if exists:
        raise ValueError(f"Barcode already exists: {barcode}")
    

# ════════════════════════════════════════════════════════════
#  ROUTING SETS  (explicit — no ambiguity)
# ════════════════════════════════════════════════════════════

# → Card table
_CARD_TYPES = {'CARD'}

# → CPU table
_CPU_TYPES = {'CPU', 'PROCESSOR'}

# → Controller table (creates a Controller record)
_CONTROLLER_TYPES = {'CONTROLLER'}

# → Memory table
_MEMORY_TYPES = {'MEMORY', 'RAM'}

# → SFP table
_SFP_TYPES = {'SFP'}

# → RailKit table
_RAILKIT_TYPES = {'RAILKIT', 'RAIL KIT'}

# → HardDisk table
_HDD_TYPES = {'HARD DISK'}

# → Spare table (ALL of these + anything not matched above)
_SPARE_TYPES = {
    'BATTERY', 'MOTHER BOARD', 'COOLING FAN', 'POWER SUPPLY',
    'RISER CARD', 'CABLE', 'CACHE MEMORY', 'COOLING FAN BACKPLANE',
    'OPTICAL DRIVE', 'HARD DISK BACKPLANE', 'HEAT SINK', 'LTO',
    'CARTRIDGE', 'ON OFF SWITCH', 'POWER BACKPLANE', 'POWER CAGE',
    'VRM', 'ADAPTOR', 'IO BOARD', 'IP PHONE',
}


# ════════════════════════════════════════════════════════════
#  CATEGORY ROUTER
# ════════════════════════════════════════════════════════════

def _route_component_to_category(product, comp_data):
    """
    Creates the correct category-specific DB record for *product*.

    Routing (first match wins):
      CARD                           → Card
      CPU / PROCESSOR                → CPU
      CONTROLLER                     → Controller
      MEMORY / RAM                   → Memory
      SFP                            → SFP
      RAILKIT / RAIL KIT             → RailKit
      HARD DISK                      → HardDisk
      Everything else                → Spare (generic)

    Returns short table-name string for display.
    """
    from apps.categories.models import (
        Spare, Card, CPU, Memory, HardDisk, SFP, RailKit,
    )

    spare_type = comp_data.get('spare_type', '').strip().upper()

    brand_name = (comp_data.get('brand') or '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    barcode = (comp_data.get('barcode') or '').strip().upper() or None

    # shared kwargs used by most models
    location_kwargs = dict(
        location           = comp_data.get('location'),
        reference_location = comp_data.get('reference_location'),
        remark             = comp_data.get('remark'),
    )

    # ── CARD ─────────────────────────────────────────────────
    if spare_type in _CARD_TYPES:
        Card.objects.create(
            product           = product,
            brand             = brand,
            oem               = comp_data.get('oem'),
            brand_model_no    = comp_data.get('model', ''),
            # model             = comp_data.get('model', ''),
            part_no           = comp_data.get('part_no'),
            alt_part_no       = comp_data.get('alt_part_no'),
            brand_serial_no_1 = comp_data.get('alt_serial_no'),
            # specs             = comp_data.get('specs'),
            interface         = None,
            capacity          = None,
            port              = None,
            barcode           = barcode,
            **location_kwargs,
        )
        return 'card'

    # ── CPU / PROCESSOR ───────────────────────────────────────
    if spare_type in _CPU_TYPES:
        CPU.objects.create(
            product       = product,
            brand         = brand,
            # model         = comp_data.get('model', ''),
            part_no       = comp_data.get('part_no'),
            no_of_cores   = None,
            no_of_threads = None,
            ghz           = None,
            frequency     = None,
            cache         = None,
            barcode       = barcode,
            **location_kwargs,
        )
        return 'cpu'

    # ── CONTROLLER ────────────────────────────────────────────
    if spare_type in _CONTROLLER_TYPES:
        from apps.categories.models import Controller
        # Controller needs its own Product (already created) + brand FK
        Controller.objects.create(
            product               = product,
            brand                 = brand,
            model                 = comp_data.get('model', ''),
            part_no               = comp_data.get('part_no'),
            alt_part_no           = comp_data.get('alt_part_no'),
            alt_serial_no         = comp_data.get('alt_serial_no'),
            specs                 = comp_data.get('specs'),
            qty                   = comp_data.get('qty') or 1,
            barcode               = barcode,
            location              = comp_data.get('location'),
            reference_location    = comp_data.get('reference_location'),
            parent_child_location = comp_data.get('parent_child_location'),
            remark                = comp_data.get('remark'),
        )
        return 'controller'

    # ── MEMORY / RAM ──────────────────────────────────────────
    if spare_type in _MEMORY_TYPES:
        Memory.objects.create(
            product    = product,
            brand      = brand,
            oem        = comp_data.get('oem'),
            model      = comp_data.get('model', ''),
            part_no_1  = comp_data.get('part_no'),
            part_no_2  = comp_data.get('alt_part_no'),
            part_no_3  = None,
            size       = None,
            ram_type   = None,
            ddr_version= None,
            frequency  = None,
            rank       = None,
            qty        = comp_data.get('qty') or 1,
            barcode    = barcode,
            **location_kwargs,
        )
        return 'memory'

    # ── SFP ───────────────────────────────────────────────────
    if spare_type in _SFP_TYPES:
        SFP.objects.create(
            product     = product,
            brand       = brand,
            model       = comp_data.get('model', ''),
            part_no     = comp_data.get('part_no'),
            description = comp_data.get('specs'),
            fibre_type  = None,
            data_rate   = None,
            barcode     = barcode,
            **location_kwargs,
        )
        return 'sfp'

    # ── RAIL KIT ──────────────────────────────────────────────
    if spare_type in _RAILKIT_TYPES:
        RailKit.objects.create(
            product         = product,
            brand           = brand,
            model           = comp_data.get('model', ''),
            part_no         = comp_data.get('part_no'),
            side            = None,
            specs           = comp_data.get('specs'),
            supported_model = None,
            qty             = comp_data.get('qty') or 1,
            barcode         = barcode,
            **location_kwargs,
        )
        return 'railkit'

    # ── HARD DISK ─────────────────────────────────────────────
    if spare_type in _HDD_TYPES:
        HardDisk.objects.create(
            product            = product,
            brand              = brand,
            oem                = comp_data.get('oem'),
            brand_model_no     = None,
            oem_model_no       = comp_data.get('model', ''),
            model              = comp_data.get('model', ''),
            part_no            = comp_data.get('part_no'),
            alt_part_no        = comp_data.get('alt_part_no'),
            alt_fru_1          = None,
            alt_fru_2          = None,
            alt_fru_3          = None,
            retail_part_no     = None,
            spare_part_tray    = None,
            gpn_code           = None,
            brand_serial_no    = None,
            oem_serial_no      = comp_data.get('alt_serial_no'),
            capacity           = None,
            rpm                = None,
            interface          = None,
            size               = None,
            firmware           = None,
            health             = comp_data.get('working_status'),
            gb_s               = None,
            barcode            = barcode,
            tray_barcode       = None,
            **location_kwargs,
        )
        return 'harddisk'

    # ── FALLBACK → generic Spare ──────────────────────────────
    # Covers all _SPARE_TYPES explicitly listed above
    # AND anything else not matched (catch-all):
    from apps.categories.models import Spare
    Spare.objects.create(
        product            = product,
        brand              = brand,
        model              = comp_data.get('model', ''),
        part_no            = comp_data.get('part_no'),
        alt_part_no        = comp_data.get('alt_part_no'),
        alt_serial_no      = comp_data.get('alt_serial_no'),
        specs              = comp_data.get('specs'),
        qty                = comp_data.get('qty') or 1,
        barcode            = barcode,
        **location_kwargs,
    )
    return 'spare'


# ════════════════════════════════════════════════════════════
#  INTERNAL HELPER — create Product + route + stock IN
# ════════════════════════════════════════════════════════════

def _create_server_component_product(comp_data,
                                      server_location,
                                      server_store_location,
                                      server_stock_status):
    """
    1. Resolve SpareCategory (get_or_create — new types auto-register)
    2. Resolve Brand (get_or_create)
    3. Create Product
    4. Route to correct category table
    5. Create InventoryTransaction (IN)

    Returns (product, category_table_name)
    """
    import uuid

    spare_type = (comp_data.get('spare_type') or '').strip().upper()

    # get_or_create — any new spare type typed by user is auto-registered
    category, _ = SpareCategory.objects.get_or_create(
        name=spare_type or 'SPARE'
    )

    brand_name = (comp_data.get('brand') or '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    barcode  = comp_data.get('barcode', '')
    model  = comp_data.get('model', '')
    serial = (comp_data.get('serial_no') or '').strip().upper()

    if not serial:
        serial = f"AUTO-{spare_type[:8]}-{uuid.uuid4().hex[:8].upper()}"

    name = (
        f"Server - {spare_type} - {barcode} - {brand_name}"
        .strip(' -')
        .replace('  ', ' ')
    )

    product = Product.objects.create(
        category  = category,
        serial_no = serial,
        part_no   = comp_data.get('part_no'),
        brand     = brand,
        model     = model,
        name      = name,
    )

    category_table = _route_component_to_category(product, comp_data)

    _create_stock_in_transaction(
        product=product,
        store_location=server_store_location or 'WH1',
        stock_status=server_stock_status or 'LIVE',
        remarks='Server component stock in',
    )

    return product, category_table


# ════════════════════════════════════════════════════════════
#  PUBLIC API 1 — create_server_with_components
# ════════════════════════════════════════════════════════════

def create_server_with_components(server_data, components):
    """
    Creates Server (cabinet) + all components in one call.

    server_data : dict  — server identity + cabinet fields + location
    components  : list of dicts — one dict per component row

    Each component is routed to the correct category table:
      CARD          → Card
      CPU/PROCESSOR → CPU
      CONTROLLER    → Controller
      MEMORY/RAM    → Memory
      SFP           → SFP
      RAILKIT       → RailKit
      HARD DISK     → HardDisk
      Everything else (BATTERY, MOTHER BOARD, COOLING FAN,
      POWER SUPPLY, RISER CARD, CABLE, CACHE MEMORY,
      COOLING FAN BACKPLANE, OPTICAL DRIVE, HARD DISK BACKPLANE,
      HEAT SINK, LTO, CARTRIDGE, ON OFF SWITCH, POWER BACKPLANE,
      POWER CAGE, VRM, ADAPTOR, IO BOARD, IP PHONE,
      + any unknown type) → Spare

    Returns: Server instance
    """
    from apps.servers.models import Server, ServerComponent
    from datetime import datetime

    store_location = server_data.get('store_location') or 'WH1'
    stock_status   = server_data.get('stock_status')   or 'LIVE'

    # ── Cabinet Product ───────────────────────────────────────
    cabinet_cat, _ = SpareCategory.objects.get_or_create(name='CABINET')

    brand_name = (server_data.get('brand') or '').strip().upper()
    brand = None
    if brand_name:
        brand, _ = Brand.objects.get_or_create(name=brand_name)

    service_tag  = (server_data.get('service_tag') or '').strip().upper()
    model        = server_data.get('model', '')

    # use explicit cabinet serial if provided, else fall back to service tag
    cabinet_serial = (
        (server_data.get('cabinet_serial_no') or '').strip().upper()
        or service_tag
    )

    cabinet_name = f"SERVER - {model} - {service_tag}".strip(' -')

    cabinet_product = Product.objects.create(
        category  = cabinet_cat,
        serial_no = cabinet_serial,
        part_no   = server_data.get('part_no'),
        brand     = brand,
        model     = model,
        name      = cabinet_name,
    )

    # ── Server record ─────────────────────────────────────────
    testing_date = None
    td_raw = server_data.get('testing_date', '')
    if td_raw:
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y'):
            try:
                testing_date = datetime.strptime(td_raw, fmt).date()
                break
            except ValueError:
                continue

    server = Server.objects.create(
        machine_type          = server_data.get('machine_type'),
        machine_no            = server_data.get('machine_no'),
        service_tag           = service_tag,
        model                 = model,
        brand                 = brand,
        # cabinet fields
        part_no               = server_data.get('part_no'),
        alt_part_no           = server_data.get('alt_part_no'),
        alt_serial_no         = server_data.get('alt_serial_no'),
        specs                 = server_data.get('specs'),
        qty                   = server_data.get('qty') or 1,
        barcode               = server_data.get('barcode') or None,
        # testing
        testing_date          = testing_date,
        tested_by             = server_data.get('tested_by'),
        # status / location
        status                = server_data.get('status') or 'WORKING',
        location              = server_data.get('location'),
        reference_location    = server_data.get('reference_location'),
        parent_child_location = server_data.get('parent_child_location'),
        remark                = server_data.get('remark'),
        product               = cabinet_product,
    )

    # ── Cabinet stock IN ──────────────────────────────────────
    _create_stock_in_transaction(
        product=cabinet_product,
        store_location=store_location,
        stock_status=stock_status,
        remarks='Server cabinet stock in',
    )

    # ── Components ────────────────────────────────────────────
    for comp in components:
        barcode = (comp.get('barcode') or '').strip().upper()
        serial  = (comp.get('serial_no') or '').strip().upper()

        if not barcode and not serial:
            continue   # skip blank rows

        # inherit server location if component fields are blank
        if not (comp.get('location') or '').strip():
            comp['location'] = server_data.get('location', '')
        if not (comp.get('reference_location') or '').strip():
            comp['reference_location'] = server_data.get('reference_location', '')

        product, _cat = _create_server_component_product(
            comp_data             = comp,
            server_location       = server_data.get('location'),
            server_store_location = store_location,
            server_stock_status   = stock_status,
        )

        ServerComponent.objects.create(
            server                = server,
            product               = product,
            spare_type            = (comp.get('spare_type') or '').strip().upper(),
            part_no               = comp.get('part_no'),
            alt_part_no           = comp.get('alt_part_no'),
            serial_no             = serial,
            alt_serial_no         = comp.get('alt_serial_no'),
            specs                 = comp.get('specs'),
            barcode               = barcode or None,
            qty                   = comp.get('qty') or 1,
            working_status        = comp.get('working_status') or 'WORKING',
            location              = comp.get('location') or server_data.get('location'),
            reference_location    = comp.get('reference_location'),
            parent_child_location = comp.get('parent_child_location'),
            remark                = comp.get('remark'),
        )

    return server


# ════════════════════════════════════════════════════════════
#  PUBLIC API 2 — add_server_component
# ════════════════════════════════════════════════════════════

def add_server_component(server, comp_data,
                          store_location='WH1',
                          stock_status='LIVE'):
    """Add a single component to an existing Server."""
    from apps.servers.models import ServerComponent

    # inherit server location if blank
    if not (comp_data.get('location') or '').strip():
        comp_data['location'] = server.location or ''
    if not (comp_data.get('reference_location') or '').strip():
        comp_data['reference_location'] = server.reference_location or ''

    product, _cat = _create_server_component_product(
        comp_data             = comp_data,
        server_location       = server.location,
        server_store_location = store_location,
        server_stock_status   = stock_status,
    )

    barcode = (comp_data.get('barcode') or '').strip().upper()
    serial  = (comp_data.get('serial_no') or '').strip().upper()

    return ServerComponent.objects.create(
        server                = server,
        product               = product,
        spare_type            = (comp_data.get('spare_type') or '').strip().upper(),
        part_no               = comp_data.get('part_no'),
        alt_part_no           = comp_data.get('alt_part_no'),
        serial_no             = serial,
        alt_serial_no         = comp_data.get('alt_serial_no'),
        specs                 = comp_data.get('specs'),
        barcode               = barcode or None,
        qty                   = comp_data.get('qty') or 1,
        working_status        = comp_data.get('working_status') or 'WORKING',
        location              = comp_data.get('location') or server.location,
        reference_location    = comp_data.get('reference_location'),
        parent_child_location = comp_data.get('parent_child_location'),
        remark                = comp_data.get('remark'),
    )
