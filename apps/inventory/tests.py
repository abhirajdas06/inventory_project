from django.test import TestCase
from django.urls import reverse

from apps.core.models import Product, SpareCategory
from apps.inventory.models import InventoryTransaction
from apps.servers.models import Server, ServerComponent


class StockOutTests(TestCase):
    def setUp(self):
        category = SpareCategory.objects.create(name='SERVER')
        component_category = SpareCategory.objects.create(name='MEMORY')

        self.server_product = Product.objects.create(
            category=category,
            serial_no='SERVER-001',
            name='Server 001',
        )
        self.component_product_1 = Product.objects.create(
            category=component_category,
            serial_no='MEM-001',
            name='Memory 001',
        )
        self.component_product_2 = Product.objects.create(
            category=component_category,
            serial_no='MEM-002',
            name='Memory 002',
        )

        self.server = Server.objects.create(
            service_tag='ST-001',
            model='PowerEdge',
            product=self.server_product,
        )
        ServerComponent.objects.create(
            server=self.server,
            product=self.component_product_1,
            spare_type='MEMORY',
            serial_no='MEM-001',
        )
        ServerComponent.objects.create(
            server=self.server,
            product=self.component_product_2,
            spare_type='MEMORY',
            serial_no='MEM-002',
        )

        for product in (
            self.server_product,
            self.component_product_1,
            self.component_product_2,
        ):
            InventoryTransaction.objects.create(
                product=product,
                transaction_type='IN',
                store_location='WH2',
                stock_status='LIVE',
            )

    def test_stocking_out_server_stocks_out_components_with_same_details(self):
        response = self.client.post(reverse('stock_out'), {
            'product_id': self.server_product.id,
            'client_name': 'Acme Corp',
            'invoice_no': 'INV-1001',
            'stock_status': 'SALE',
            'stock_out_date': '2026-05-27',
        })

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'success': True,
                'status': 'SALE',
                'components_stocked_out': 2,
            },
        )

        for product in (
            self.server_product,
            self.component_product_1,
            self.component_product_2,
        ):
            latest = InventoryTransaction.objects.filter(
                product=product
            ).order_by('-created_at').first()

            self.assertEqual(latest.transaction_type, 'OUT')
            self.assertEqual(latest.store_location, 'WH2')
            self.assertEqual(latest.stock_status, 'SALE')
            self.assertEqual(str(latest.stock_out_date), '2026-05-27')
            self.assertEqual(latest.client_name, 'Acme Corp')
            self.assertEqual(latest.invoice_no, 'INV-1001')

    def test_stocking_out_regular_product_does_not_stock_out_server_components(self):
        category = SpareCategory.objects.create(name='SPARE')
        product = Product.objects.create(
            category=category,
            serial_no='SPARE-001',
            name='Regular Spare',
        )
        InventoryTransaction.objects.create(
            product=product,
            transaction_type='IN',
            store_location='WH1',
            stock_status='LIVE',
        )

        response = self.client.post(reverse('stock_out'), {
            'product_id': product.id,
            'client_name': 'Regular Client',
            'invoice_no': 'INV-2001',
            'stock_status': 'RENT',
            'stock_out_date': '2026-05-27',
        })

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'success': True,
                'status': 'RENT',
                'components_stocked_out': 0,
            },
        )

        self.assertEqual(
            InventoryTransaction.objects.filter(
                transaction_type='OUT'
            ).count(),
            1,
        )

        latest = InventoryTransaction.objects.filter(
            product=product
        ).order_by('-created_at').first()

        self.assertEqual(latest.transaction_type, 'OUT')
        self.assertEqual(latest.stock_status, 'RENT')
        self.assertEqual(latest.client_name, 'Regular Client')

    def test_stocked_out_server_moves_from_active_list_to_sold_list(self):
        active_response = self.client.get(reverse('server_list'))
        self.assertContains(active_response, 'ST-001')

        self.client.post(reverse('stock_out'), {
            'product_id': self.server_product.id,
            'client_name': 'Acme Corp',
            'invoice_no': 'INV-1001',
            'stock_status': 'SALE',
            'stock_out_date': '2026-05-27',
        })

        active_response = self.client.get(reverse('server_list'))
        sold_response = self.client.get(reverse('server_out_list'))

        self.assertNotContains(active_response, 'ST-001')
        self.assertContains(sold_response, 'ST-001')
        self.assertContains(sold_response, 'Acme Corp')
        self.assertContains(sold_response, 'INV-1001')
