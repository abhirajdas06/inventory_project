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
