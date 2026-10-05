from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from apps.core.models import Product, SpareCategory, UserProfile
from apps.categories.models import Spare
from apps.inventory.models import InventoryTransaction
from apps.servers.models import Server, ServerComponent
from apps.servers.views import _server_queryset


class EmptyServerTests(TestCase):
    """A server with no motherboard currently mapped and in stock is
    "Empty" — shown with an EMPTY status, highlighted gray, and listed on
    the Empty tab instead of the Live tab. This is fully derived from live
    ServerComponent + InventoryTransaction data, so mapping/unmapping/
    stocking a motherboard in or out moves the server between tabs
    automatically with no extra flag to maintain."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='mbtester', password='pass12345', email='mbtester@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)

        self.cabinet_category = SpareCategory.objects.create(name='CABINET-MB')
        self.mb_category = SpareCategory.objects.create(name='MOTHER BOARD')
        self.mem_category = SpareCategory.objects.create(name='MEMORY-MB')

    def _make_server(self, tag, model='R630', with_motherboard=False):
        cabinet_product = Product.objects.create(
            category=self.cabinet_category, serial_no=tag, name=f'Server {tag}',
        )
        server = Server.objects.create(service_tag=tag, model=model, product=cabinet_product)
        InventoryTransaction.objects.create(
            product=cabinet_product, transaction_type='IN', store_location='WH1', stock_status='LIVE',
        )
        if with_motherboard:
            mb_product = Product.objects.create(
                category=self.mb_category, serial_no=f'{tag}-MB', name=f'Motherboard {tag}',
            )
            InventoryTransaction.objects.create(
                product=mb_product, transaction_type='IN', store_location='WH1', stock_status='LIVE',
            )
            ServerComponent.objects.create(
                server=server, product=mb_product, spare_type='MOTHER BOARD', serial_no=f'{tag}-MB',
            )
        return server

    def test_server_without_motherboard_is_empty(self):
        server = self._make_server('EMPTY-001', with_motherboard=False)
        annotated = _server_queryset().get(id=server.id)
        self.assertFalse(annotated.has_motherboard)

        live = self.client.get(reverse('server_list'))
        empty = self.client.get(reverse('server_empty_list'))
        self.assertNotContains(live, 'EMPTY-001')
        self.assertContains(empty, 'EMPTY-001')
        self.assertContains(empty, 'EMPTY')  # status badge text

    def test_server_with_motherboard_is_live(self):
        server = self._make_server('LIVE-001', with_motherboard=True)
        annotated = _server_queryset().get(id=server.id)
        self.assertTrue(annotated.has_motherboard)

        live = self.client.get(reverse('server_list'))
        empty = self.client.get(reverse('server_empty_list'))
        self.assertContains(live, 'LIVE-001')
        self.assertNotContains(empty, 'LIVE-001')

    def test_mapping_motherboard_moves_server_from_empty_to_live(self):
        server = self._make_server('MAP-001', with_motherboard=False)
        self.assertContains(self.client.get(reverse('server_empty_list')), 'MAP-001')

        mb_product = Product.objects.create(
            category=self.mb_category, serial_no='MAP-001-MB', name='Loose Motherboard',
        )
        InventoryTransaction.objects.create(
            product=mb_product, transaction_type='IN', store_location='WH1', stock_status='LIVE',
        )

        response = self.client.post(reverse('map_inventory'), {
            'product_id': mb_product.id,
            'target_type': 'server',
            'target_id': server.id,
            'remarks': 'Installed replacement motherboard',
        })
        self.assertTrue(response.json()['success'])

        self.assertContains(self.client.get(reverse('server_list')), 'MAP-001')
        self.assertNotContains(self.client.get(reverse('server_empty_list')), 'MAP-001')

    def test_stocking_out_motherboard_moves_server_to_empty(self):
        server = self._make_server('OUT-001', with_motherboard=True)
        self.assertContains(self.client.get(reverse('server_list')), 'OUT-001')

        mb_component = server.components.get(spare_type='MOTHER BOARD')
        response = self.client.post(reverse('stock_out'), {
            'product_id': mb_component.product_id,
            'client_name': 'RMA',
            'stock_status': 'FAULTY',
            'stock_out_date': '2026-01-01',
        })
        self.assertTrue(response.json()['success'])

        self.assertNotContains(self.client.get(reverse('server_list')), 'OUT-001')
        self.assertContains(self.client.get(reverse('server_empty_list')), 'OUT-001')

    def test_search_splits_live_and_empty_counts(self):
        self._make_server('R630-A', model='PowerEdge R630', with_motherboard=True)
        self._make_server('R630-B', model='PowerEdge R630', with_motherboard=True)
        self._make_server('R630-C', model='PowerEdge R630', with_motherboard=False)

        live_response = self.client.get(reverse('server_list'), {'q': 'R630'})
        empty_response = self.client.get(reverse('server_empty_list'), {'q': 'R630'})

        self.assertEqual(live_response.context['live_count'], 2)
        self.assertEqual(live_response.context['empty_count'], 1)
        self.assertEqual(empty_response.context['live_count'], 2)
        self.assertEqual(empty_response.context['empty_count'], 1)


class ServerGroupTests(TestCase):
    """Servers are split into groups (Rack Server, Storage, Networking
    Switch, ...) with a per-group Empty rule -- see apps.servers.groups."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='grp', password='pass12345', email='g@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        self.cab = SpareCategory.objects.create(name='CABINET-G')
        self.part = SpareCategory.objects.create(name='PART-G')
        self.n = 0

    def _server(self, tag, group, machine_type='RACK SERVER', model='X'):
        p = Product.objects.create(category=self.cab, serial_no=tag, name=tag)
        InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')
        return Server.objects.create(service_tag=tag, group=group, machine_type=machine_type, model=model, product=p)

    def _part(self, server, spare_type):
        self.n += 1
        p = Product.objects.create(category=self.part, serial_no=f'P-{self.n}', name=spare_type)
        InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')
        ServerComponent.objects.create(server=server, product=p, spare_type=spare_type, serial_no=f'P-{self.n}')
        return p

    def _stock_out(self, product):
        InventoryTransaction.objects.create(product=product, transaction_type='OUT', store_location='WH1', stock_status='SALE')

    def _empty(self, server):
        return _server_queryset().get(pk=server.pk).is_empty

    def test_motherboard_rule_for_rack_blade_sun(self):
        for group in ('rack_server', 'blade_server', 'sun_servers'):
            s = self._server(f'MB-{group}', group)
            self.assertTrue(self._empty(s), group)
            mb = self._part(s, 'MOTHER BOARD')
            self.assertFalse(self._empty(s), group)
            self._stock_out(mb)
            self.assertTrue(self._empty(s), group)
            self._part(s, 'MOTHER BOARD')  # newly mapped motherboard -> live again
            self.assertFalse(self._empty(s), group)

    def test_storage_needs_at_least_one_controller_and_one_power_supply(self):
        s = self._server('STG-1', 'storage', machine_type='STORAGE')
        c1, c2 = self._part(s, 'CONTROLLER'), self._part(s, 'CONTROLLER')
        p1, p2 = self._part(s, 'POWER SUPPLY'), self._part(s, 'POWER SUPPLY')
        self.assertFalse(self._empty(s))
        self._stock_out(c1)
        self._stock_out(p1)
        self.assertFalse(self._empty(s))  # one controller + one PSU is still live
        self._stock_out(c2)
        self.assertTrue(self._empty(s))   # both controllers gone
        self._part(s, 'CONTROLLER')
        self.assertFalse(self._empty(s))  # new controller mapped -> live
        self._stock_out(p2)
        self.assertTrue(self._empty(s))   # both power supplies gone
        self._part(s, 'POWERSUPPLY')
        self.assertFalse(self._empty(s))

    def test_tape_library_needs_an_lto_or_tape_drive(self):
        s = self._server('TAPE-1', 'storage', machine_type='TAPE LIBRARY')
        lto1, lto2 = self._part(s, 'LTO'), self._part(s, 'TAPE DRIVE')
        self.assertFalse(self._empty(s))  # no controller/PSU needed for a tape library
        self._stock_out(lto1)
        self.assertFalse(self._empty(s))
        self._stock_out(lto2)
        self.assertTrue(self._empty(s))
        self._part(s, 'LTO')
        self.assertFalse(self._empty(s))

    def test_other_groups_are_never_empty(self):
        for group in ('desktop', 'cisco_chassis', 'hp_ibm_dell_chassis',
                      'networking_firewall', 'networking_router_modem', 'networking_switch'):
            self.assertFalse(self._empty(self._server(f'NE-{group}', group)), group)

    def test_group_lists_are_scoped_and_tabs_split_live_empty(self):
        rack_live = self._server('RACK-LIVE', 'rack_server')
        self._part(rack_live, 'MOTHER BOARD')
        self._server('RACK-EMPTY', 'rack_server')
        self._server('SW-1', 'networking_switch', machine_type='SWITCH')

        live = self.client.get(reverse('server_group_list', args=['rack_server']))
        self.assertContains(live, 'RACK-LIVE')
        self.assertNotContains(live, 'RACK-EMPTY')
        self.assertNotContains(live, 'SW-1')
        self.assertEqual((live.context['live_count'], live.context['empty_count']), (1, 1))

        empty = self.client.get(reverse('server_group_empty_list', args=['rack_server']))
        self.assertContains(empty, 'RACK-EMPTY')
        self.assertContains(empty, 'No motherboard in stock')

        self.assertContains(self.client.get(reverse('server_group_list', args=['networking_switch'])), 'SW-1')
        self.assertEqual(self.client.get('/servers/g/not_a_group/').status_code, 404)

    def test_sold_list_scoped_to_group(self):
        a = self._server('SOLD-RACK', 'rack_server')
        b = self._server('SOLD-SW', 'networking_switch')
        self._stock_out(a.product)
        self._stock_out(b.product)
        html = self.client.get(reverse('server_group_out_list', args=['rack_server'])).content.decode()
        self.assertIn('SOLD-RACK', html)
        self.assertNotIn('SOLD-SW', html)


class InferServerGroupTests(TestCase):
    def test_inference_from_machine_type_and_model(self):
        from apps.servers.groups import infer_server_group as f
        self.assertEqual(f('BLADE SERVER', 'HP BL460'), 'blade_server')
        self.assertEqual(f('CHASSIS', 'CISCO UCS 5108'), 'cisco_chassis')
        self.assertEqual(f('CHASISS', 'HP SYNERGY 12000'), 'hp_ibm_dell_chassis')
        self.assertEqual(f('DESKTOP', ''), 'desktop')
        self.assertEqual(f('TAPE LIBRARY', 'IBM TS4300'), 'storage')
        self.assertEqual(f('ROUTER', ''), 'networking_router_modem')
        self.assertEqual(f('MODEM', ''), 'networking_router_modem')
        self.assertEqual(f('SWITCH', ''), 'networking_switch')
        self.assertEqual(f('FIREWALL', ''), 'networking_firewall')
        self.assertEqual(f('RACK SERVER', 'SUN FIRE X4170'), 'sun_servers')
        self.assertEqual(f('TOWER SERVER', 'SPARC ENTERPRISE T2000'), 'sun_servers')
        self.assertEqual(f('RACK SERVER', 'DELL R740'), 'rack_server')
        self.assertEqual(f('WORKSTATION', 'DELL T7820'), 'rack_server')
