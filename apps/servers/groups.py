"""Server groups (Blade Server, Storage, Networking Switch, ...) and the
per-group "Empty" rule.

Every server row stores its group in ``Server.group``. The group-specific
import options set it directly; the generic Server import (and the one-off
back-fill migration) infer it from Machine Type / Model with
``infer_server_group``.

Empty rules — fully derived from live component stock, so mapping a part
back in moves the machine straight back to Live with nothing to update:

* Rack / Blade / Sun servers: Empty when no motherboard is in stock in it.
* Storage: Empty when it has no in-stock controller OR no in-stock power
  supply (one controller + one PSU is still Live).
* Tape library / LTO (Machine Type TAPE LIBRARY, LTO, TAPE DRIVE, inside the
  Storage group): Empty when no LTO / tape drive is in stock in it.
* Every other group (Desktop, Chassis, Networking): never Empty.
"""
from collections import OrderedDict

from django.db.models import BooleanField, Case, Exists, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Upper

# Order = sidebar / dashboard order (as listed by the business).
SERVER_GROUPS = OrderedDict([
    ('blade_server', {'label': 'Blade Server', 'icon': 'bi-layers'}),
    ('cisco_chassis', {'label': 'Cisco Chassis', 'icon': 'bi-hdd-rack'}),
    ('desktop', {'label': 'Desktop', 'icon': 'bi-pc-display'}),
    ('hp_ibm_dell_chassis', {'label': 'HP-IBM-DELL Chassis', 'icon': 'bi-hdd-rack-fill'}),
    ('rack_server', {'label': 'Rack Server', 'icon': 'bi-hdd-network'}),
    ('storage', {'label': 'Storage', 'icon': 'bi-database'}),
    ('sun_servers', {'label': 'Sun Servers', 'icon': 'bi-sun'}),
    ('networking_firewall', {'label': 'Networking Firewall', 'icon': 'bi-shield-lock'}),
    ('networking_router_modem', {'label': 'Networking Router & Modem', 'icon': 'bi-router'}),
    ('networking_switch', {'label': 'Networking Switch', 'icon': 'bi-diagram-3'}),
])

GROUP_CHOICES = tuple((slug, cfg['label']) for slug, cfg in SERVER_GROUPS.items())

MOTHERBOARD_RULE_GROUPS = ('rack_server', 'blade_server', 'sun_servers')
STORAGE_GROUP = 'storage'

MOTHERBOARD_SPARE_TYPES = ['MOTHER BOARD', 'MOTHERBOARD', 'MAIN BOARD', 'SYSTEM BOARD']
CONTROLLER_SPARE_TYPES = ['CONTROLLER', 'CONTROLER']
POWER_SUPPLY_SPARE_TYPES = ['POWER SUPPLY', 'POWERSUPPLY']
TAPE_DRIVE_SPARE_TYPES = ['LTO', 'TAPE DRIVE', 'LTO TAPE DRIVE', 'LTO DRIVE']
TAPE_LIBRARY_MACHINE_TYPES = ['TAPE LIBRARY', 'LTO', 'TAPE DRIVE']

def infer_server_group(machine_type, model=''):
    """Best guess at a server's group from its Machine Type and Model — used
    by the generic Server import and the back-fill of existing servers. The
    group-specific imports don't need it: the chosen option sets the group."""
    mt = ' '.join(str(machine_type or '').upper().split())
    mo = ' '.join(str(model or '').upper().split())
    if mt == 'BLADE SERVER':
        return 'blade_server'
    if mt in ('CHASSIS', 'CHASISS', 'CHASIS'):
        return 'cisco_chassis' if 'CISCO' in mo else 'hp_ibm_dell_chassis'
    if mt == 'DESKTOP':
        return 'desktop'
    if mt in ('STORAGE', *TAPE_LIBRARY_MACHINE_TYPES):
        return 'storage'
    if mt == 'FIREWALL':
        return 'networking_firewall'
    if mt in ('ROUTER', 'MODEM'):
        return 'networking_router_modem'
    if mt == 'SWITCH':
        return 'networking_switch'
    if mo.startswith('SUN ') or any(h in mo for h in ('SPARC', 'NETRA', 'ORACLE')):
        return 'sun_servers'
    return 'rack_server'


def _component_in_stock(spare_types):
    from apps.inventory.models import InventoryTransaction
    from apps.servers.models import ServerComponent

    return Exists(
        ServerComponent.objects.filter(server=OuterRef('pk'), spare_type__in=spare_types)
        .annotate(comp_latest_type=Subquery(
            InventoryTransaction.objects.filter(product=OuterRef('product'))
            .order_by('-created_at').values('transaction_type')[:1]
        ))
        .exclude(comp_latest_type='OUT')
    )


def annotate_empty(queryset):
    """Adds has_motherboard / has_controller / has_power_supply /
    has_tape_drive and the combined ``is_empty`` flag to a Server queryset."""
    queryset = queryset.annotate(
        has_motherboard=_component_in_stock(MOTHERBOARD_SPARE_TYPES),
        has_controller=_component_in_stock(CONTROLLER_SPARE_TYPES),
        has_power_supply=_component_in_stock(POWER_SUPPLY_SPARE_TYPES),
        has_tape_drive=_component_in_stock(TAPE_DRIVE_SPARE_TYPES),
        machine_type_upper=Upper('machine_type'),
    )
    motherboard_groups = Q(group__in=MOTHERBOARD_RULE_GROUPS) | Q(group='') | Q(group__isnull=True)
    tape_library = Q(machine_type_upper__in=TAPE_LIBRARY_MACHINE_TYPES)
    return queryset.annotate(is_empty=Case(
        When(motherboard_groups & Q(has_motherboard=False), then=Value(True)),
        When(Q(group=STORAGE_GROUP) & tape_library & Q(has_tape_drive=False), then=Value(True)),
        When(
            Q(group=STORAGE_GROUP) & ~tape_library & (Q(has_controller=False) | Q(has_power_supply=False)),
            then=Value(True),
        ),
        default=Value(False),
        output_field=BooleanField(),
    ))


def empty_reason(server):
    """Plain-language reason a server is Empty (tooltip / badge text)."""
    group = server.group or 'rack_server'
    if group in MOTHERBOARD_RULE_GROUPS:
        return 'No motherboard in stock'
    if group == STORAGE_GROUP:
        if (server.machine_type or '').upper() in TAPE_LIBRARY_MACHINE_TYPES:
            return 'No LTO / tape drive in stock'
        missing = []
        if not getattr(server, 'has_controller', True):
            missing.append('controller')
        if not getattr(server, 'has_power_supply', True):
            missing.append('power supply')
        return 'No ' + ' or '.join(missing) + ' in stock' if missing else 'Empty'
    return 'Empty'
