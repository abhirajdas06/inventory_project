from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from openpyxl import Workbook

from apps.core.models import ActivityLog, AssetTimelineEvent, UserProfile
from apps.core.models import Product, SpareCategory
from apps.categories.models import Spare
from apps.inventory.models import InventoryFreezeRecord, InventoryTransaction, InventoryTransfer, RentalRecord, SalesReturn, TransferRequest
from apps.servers.models import Server, ServerComponent
from apps.core.permissions import has_permission


class RolePermissionTests(TestCase):
    def _user(self, username, role):
        user = User.objects.create_user(username=username, password='pass12345')
        UserProfile.objects.create(user=user, role=role)
        return user

    def test_role_capabilities_follow_inventory_responsibilities(self):
        stock_in = self._user('stock-in', 'STOCK_IN')
        stock_out = self._user('stock-out', 'STOCK_OUT')
        audit = self._user('audit', 'AUDIT')
        admin = self._user('admin', 'ADMIN')

        self.assertTrue(has_permission(stock_in, 'stock_in'))
        self.assertTrue(has_permission(stock_in, 'sales_return'))
        self.assertTrue(has_permission(stock_in, 'rent_return'))
        self.assertTrue(has_permission(stock_in, 'transfer_receive'))
        self.assertTrue(has_permission(stock_in, 'mapping'))
        self.assertTrue(has_permission(stock_in, 'stock_return'))
        self.assertFalse(has_permission(stock_in, 'stock_out'))
        self.assertFalse(has_permission(stock_in, 'transfer_request'))
        self.assertFalse(has_permission(stock_in, 'stock_out_import'))

        self.assertTrue(has_permission(stock_out, 'stock_out'))
        self.assertTrue(has_permission(stock_out, 'stock_out_import'))
        self.assertTrue(has_permission(stock_out, 'transfer_request'))
        self.assertTrue(has_permission(stock_out, 'freeze'))
        self.assertTrue(has_permission(stock_out, 'mapping'))
        self.assertFalse(has_permission(stock_out, 'stock_return'))
        self.assertFalse(has_permission(stock_out, 'transfer_receive'))

        self.assertTrue(has_permission(audit, 'audit'))
        self.assertTrue(has_permission(audit, 'audit_findings'))
        self.assertFalse(has_permission(audit, 'reconciliation'))
        self.assertTrue(has_permission(admin, 'reconciliation'))
        self.assertTrue(has_permission(admin, 'transfer_request'))
        self.assertTrue(has_permission(admin, 'transfer_receive'))


class StockOutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass12345')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
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
            'olf_dc_number': 'OLF-1001',
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
            self.assertEqual(latest.olf_dc_number, 'OLF-1001')
            self.assertEqual(latest.performed_by, self.user)

        self.assertTrue(ActivityLog.objects.filter(action='STOCK_OUT', entity_id=str(self.server_product.id)).exists())
        self.assertTrue(AssetTimelineEvent.objects.filter(product=self.server_product, event_type='OUT').exists())

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

    def test_audit_stores_result_and_creates_activity_and_timeline(self):
        response = self.client.post(reverse('audit_spare'), {
            'product_id': self.server_product.id,
            'audit_remark': 'Checked rack',
            'audited_on': '2026-05-27',
            'audit_result': 'FOUND',
        })

        self.assertEqual(response.status_code, 200)
        latest = InventoryTransaction.objects.filter(
            product=self.server_product,
            transaction_type='AUDIT',
        ).latest('created_at')
        self.assertEqual(latest.audit_result, 'FOUND')
        self.assertTrue(ActivityLog.objects.filter(action='AUDIT', entity_id=str(self.server_product.id)).exists())
        self.assertTrue(AssetTimelineEvent.objects.filter(product=self.server_product, event_type='AUDIT').exists())

    def test_single_transfer_creates_pending_request_and_activity(self):
        response = self.client.post(reverse('transfer_inventory'), {
            'product_id': self.server_product.id,
            'destination_warehouse': 'WH1',
            'remarks': 'Moved for staging',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(response.json()['transfer_request_id'])
        self.assertTrue(TransferRequest.objects.filter(items__product=self.server_product, status='PENDING').exists())
        self.assertFalse(InventoryTransfer.objects.filter(product=self.server_product).exists())
        self.assertTrue(ActivityLog.objects.filter(action='TRANSFER_REQUEST', entity_id=str(self.server_product.id)).exists())
        self.assertTrue(AssetTimelineEvent.objects.filter(product=self.server_product, event_type='TRANSFER').exists())

    def test_single_transfer_does_not_update_location_until_receipt(self):
        category = SpareCategory.objects.create(name='SPARE-TX')
        product = Product.objects.create(
            category=category,
            serial_no='SPARE-TX-001',
            name='Transfer Spare',
        )
        spare = Spare.objects.create(
            product=product,
            part_no='TX-100',
            barcode='TX-BC-100',
            location='Rack 1',
        )
        InventoryTransaction.objects.create(
            product=product,
            transaction_type='IN',
            store_location='WH1',
            stock_status='LIVE',
        )

        response = self.client.post(reverse('transfer_inventory'), {
            'product_id': product.id,
            'destination_warehouse': 'WH2',
            'remarks': 'Relocated',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        spare.refresh_from_db()
        self.assertEqual(spare.location, 'Rack 1')
        latest = InventoryTransaction.objects.filter(product=product).order_by('-created_at').first()
        self.assertEqual(latest.store_location, 'WH1')

    def test_single_transfer_receipt_updates_location_on_approval(self):
        category = SpareCategory.objects.create(name='SPARE-TX-RECEIVE')
        product = Product.objects.create(
            category=category,
            serial_no='SPARE-TX-R-001',
            name='Manual Transfer Spare',
        )
        Spare.objects.create(
            product=product,
            part_no='TX-R-100',
            barcode='TX-R-BC-100',
            location='Rack 1',
        )
        InventoryTransaction.objects.create(
            product=product,
            transaction_type='IN',
            store_location='WH1',
            stock_status='LIVE',
        )

        response = self.client.post(reverse('transfer_inventory'), {
            'product_id': product.id,
            'destination_warehouse': 'WH2',
            'remarks': 'Move to warehouse 2',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        transfer_request = TransferRequest.objects.get(id=response.json()['transfer_request_id'])
        item = transfer_request.items.get(product=product)
        self.assertEqual(item.destination_location, '')
        self.assertFalse(InventoryTransfer.objects.filter(product=product).exists())

        receipt = self.client.post(reverse('receive_transfer_item', args=[transfer_request.id, item.id]), {
            'destination_location': 'WH2/Rack 8',
        })

        self.assertEqual(receipt.status_code, 200)
        self.assertTrue(receipt.json()['success'])
        transfer_request.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(transfer_request.status, 'COMPLETED')
        self.assertEqual(item.destination_location, 'WH2/Rack 8')
        self.assertEqual(Spare.objects.get(product=product).location, 'WH2/Rack 8')
        latest = InventoryTransaction.objects.filter(product=product).order_by('-created_at').first()
        self.assertEqual(latest.transaction_type, 'IN')
        self.assertEqual(latest.store_location, 'WH2')
        self.assertTrue(InventoryTransfer.objects.filter(product=product, destination_location='WH2/Rack 8').exists())

    def test_frozen_stock_out_with_allow_frozen_releases_freeze(self):
        InventoryFreezeRecord.objects.create(
            product=self.server_product,
            status='FROZEN',
            reason='Audit hold',
            frozen_by=self.user,
        )

        response = self.client.post(reverse('stock_out'), {
            'product_id': self.server_product.id,
            'client_name': 'Acme Corp',
            'invoice_no': 'INV-FZ-1',
            'stock_status': 'SCRAP',
            'stock_out_date': '2026-05-27',
            'allow_frozen': '1',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        latest_txn = InventoryTransaction.objects.filter(
            product=self.server_product
        ).order_by('-created_at').first()
        self.assertEqual(latest_txn.transaction_type, 'OUT')
        latest_freeze = InventoryFreezeRecord.objects.filter(
            product=self.server_product
        ).latest('frozen_at')
        self.assertEqual(latest_freeze.status, 'UNFROZEN')

    def test_rent_out_then_return_makes_item_available_again(self):
        category = SpareCategory.objects.create(name='SPARE-RENT')
        product = Product.objects.create(category=category, serial_no='RENT-1', name='Rental Spare')
        Spare.objects.create(product=product, barcode='RENT-BC-1', location='L1')
        InventoryTransaction.objects.create(
            product=product, transaction_type='IN', store_location='WH1', stock_status='LIVE',
        )

        # Rent out
        resp = self.client.post(reverse('stock_out'), {
            'product_id': product.id,
            'client_name': 'Renter Inc',
            'invoice_no': 'INV-R1',
            'stock_status': 'RENT',
            'stock_out_date': '2026-06-01',
            'expected_return_date': '2026-06-30',
        })
        self.assertTrue(resp.json()['success'])
        rental = RentalRecord.objects.get(product=product)
        self.assertEqual(rental.status, 'ON_RENT')
        self.assertEqual(str(rental.expected_return_date), '2026-06-30')
        latest = InventoryTransaction.objects.filter(product=product).latest('created_at')
        self.assertEqual(latest.transaction_type, 'OUT')

        # Return
        resp = self.client.post(reverse('return_rental'), {
            'rental_id': rental.id,
            'return_date': '2026-06-20',
            'remarks': 'returned',
        })
        self.assertTrue(resp.json()['success'])
        rental.refresh_from_db()
        self.assertEqual(rental.status, 'RETURNED')
        self.assertEqual(str(rental.actual_return_date), '2026-06-20')
        latest = InventoryTransaction.objects.filter(product=product).latest('created_at')
        self.assertEqual(latest.transaction_type, 'IN')  # available again
        spare = Spare.objects.get(product=product)
        spare.refresh_from_db()
        self.assertIn('2026-06-20 - returned', spare.remark)
        self.assertTrue(ActivityLog.objects.filter(action='RENT_RETURN', entity_id=str(product.id)).exists())

    def test_frozen_product_cannot_be_stocked_out(self):
        InventoryFreezeRecord.objects.create(
            product=self.server_product,
            status='FROZEN',
            reason='Audit hold',
            frozen_by=self.user,
        )

        response = self.client.post(reverse('stock_out'), {
            'product_id': self.server_product.id,
            'client_name': 'Acme Corp',
            'invoice_no': 'INV-3001',
            'stock_status': 'SALE',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['success'])
        self.assertIn('Frozen stock', response.json()['error'])

    def test_frozen_server_is_hidden_from_active_list(self):
        InventoryFreezeRecord.objects.create(
            product=self.server_product,
            status='FROZEN',
            reason='Audit hold',
            frozen_by=self.user,
        )

        response = self.client.get(reverse('server_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'ST-001')

    def test_frozen_spare_is_hidden_from_active_list(self):
        category = SpareCategory.objects.create(name='SPARE')
        product = Product.objects.create(
            category=category,
            serial_no='SPARE-FROZEN-001',
            name='Frozen Spare',
        )
        Spare.objects.create(
            product=product,
            part_no='FS-100',
            barcode='FS-BC-100',
        )
        InventoryTransaction.objects.create(
            product=product,
            transaction_type='IN',
            store_location='WH1',
            stock_status='LIVE',
        )
        InventoryFreezeRecord.objects.create(
            product=product,
            status='FROZEN',
            reason='Audit hold',
            frozen_by=self.user,
        )

        response = self.client.get(reverse('spare_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'SPARE-FROZEN-001')

    def test_unfreeze_form_redirects_back_to_frozen_list(self):
        InventoryFreezeRecord.objects.create(
            product=self.server_product,
            status='FROZEN',
            reason='Audit hold',
            frozen_by=self.user,
        )

        response = self.client.post(reverse('unfreeze_inventory'), {
            'product_id': self.server_product.id,
            'reason': 'Released after audit',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('frozen_inventory_list'))
        latest = InventoryFreezeRecord.objects.filter(product=self.server_product).latest('frozen_at')
        self.assertEqual(latest.status, 'UNFROZEN')

    def test_sales_return_normal_makes_sold_server_and_components_live(self):
        self.client.post(reverse('stock_out'), {'product_id': self.server_product.id, 'stock_status': 'SALE'})
        response = self.client.post(reverse('sales_return'), {
            'product_id': self.server_product.id, 'reason': 'NORMAL', 'returned_on': '2026-07-01', 'remarks': 'Customer changed requirement',
        })
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['components_returned'], 2)
        for product in (self.server_product, self.component_product_1, self.component_product_2):
            latest = product.transactions.latest('created_at')
            self.assertEqual(latest.transaction_type, 'IN')
            self.assertEqual(latest.stock_status, 'LIVE')
        self.assertEqual(SalesReturn.objects.filter(product=self.server_product).count(), 1)

    def test_sales_return_faulty_goes_to_faulty_stock(self):
        self.client.post(reverse('stock_out'), {'product_id': self.server_product.id, 'stock_status': 'SALE'})
        response = self.client.post(reverse('sales_return'), {
            'product_id': self.server_product.id, 'reason': 'FAULTY', 'returned_on': '2026-07-01',
        })
        self.assertTrue(response.json()['success'])
        latest = self.server_product.transactions.latest('created_at')
        self.assertEqual(latest.stock_status, 'FAULTY')

    def test_sales_return_stores_dated_remarks(self):
        self.client.post(reverse('stock_out'), {'product_id': self.server_product.id, 'stock_status': 'SALE'})
        response = self.client.post(reverse('sales_return'), {
            'product_id': self.server_product.id,
            'reason': 'NORMAL',
            'returned_on': '2026-07-03',
            'remarks': 'Customer accepted replacement',
        })
        self.assertTrue(response.json()['success'])
        record = SalesReturn.objects.filter(product=self.server_product).latest('created_at')
        self.assertIn('2026-07-03 - Customer accepted replacement', record.remarks)
        self.server.refresh_from_db()
        self.assertIn('2026-07-03 - Customer accepted replacement', self.server.remark)

    def test_sales_return_allows_warehouse_and_location_update(self):
        category = SpareCategory.objects.create(name='RETURN-SPARE')
        product = Product.objects.create(
            category=category,
            serial_no='RETURN-001',
            name='Return item',
        )
        spare = Spare.objects.create(
            product=product,
            barcode='RETURN-BC-1',
            location='Old Rack',
            part_no='PN-RETURN',
        )
        InventoryTransaction.objects.create(
            product=product,
            transaction_type='IN',
            store_location='WH1',
            stock_status='LIVE',
            performed_by=self.user,
        )
        self.client.post(reverse('stock_out'), {
            'product_id': product.id,
            'stock_status': 'SALE',
            'stock_out_date': '2026-07-01',
        })
        response = self.client.post(reverse('sales_return'), {
            'product_id': product.id,
            'reason': 'NORMAL',
            'returned_on': '2026-07-02',
            'location': 'WH2',
            'physical_location': 'Rack 9 / Shelf 2',
            'remarks': 'Moved back to staging',
        })
        self.assertTrue(response.json()['success'])
        latest = product.transactions.latest('created_at')
        self.assertEqual(latest.transaction_type, 'IN')
        self.assertEqual(latest.store_location, 'WH2')
        spare.refresh_from_db()
        self.assertEqual(spare.location, 'Rack 9 / Shelf 2')

    def test_stock_out_user_can_scrap_faulty_stock_and_components(self):
        self.client.post(reverse('stock_out'), {
            'product_id': self.server_product.id,
            'stock_status': 'FAULTY',
            'stock_out_date': '2026-07-01',
            'remarks': 'Initial faulty move',
        })
        response = self.client.post(reverse('scrap_faulty_stock'), {
            'product_id': self.server_product.id,
            'scrapped_on': '2026-07-02',
            'remarks': 'Scrap after inspection',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['status'], 'SCRAP')
        for product in (self.server_product, self.component_product_1, self.component_product_2):
            latest = product.transactions.latest('created_at')
            self.assertEqual(latest.transaction_type, 'OUT')
            self.assertEqual(latest.stock_status, 'SCRAP')

    def test_stock_in_user_cannot_scrap_faulty_stock(self):
        stock_in = User.objects.create_user(username='stockin', password='pass12345')
        UserProfile.objects.create(user=stock_in, role='STOCK_IN')
        self.client.force_login(stock_in)
        self.client.post(reverse('stock_out'), {
            'product_id': self.server_product.id,
            'stock_status': 'FAULTY',
            'stock_out_date': '2026-07-01',
        })
        response = self.client.post(reverse('scrap_faulty_stock'), {
            'product_id': self.server_product.id,
            'scrapped_on': '2026-07-02',
        })
        self.assertEqual(response.status_code, 403)

    def test_transfer_receipt_updates_only_requested_barcode_location(self):
        category = SpareCategory.objects.create(name='TRANSFER-SPARE')
        product = Product.objects.create(category=category, serial_no='TR-1', name='Transfer item')
        Spare.objects.create(product=product, barcode='TR-BC-1', location='Rack 1')
        InventoryTransaction.objects.create(product=product, transaction_type='IN', store_location='WH1', stock_status='LIVE')
        def xlsx(headers, row):
            book = Workbook(); sheet = book.active; sheet.append(headers); sheet.append(row); buffer = BytesIO(); book.save(buffer); buffer.seek(0)
            return SimpleUploadedFile('transfer.xlsx', buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        create = self.client.post(reverse('create_transfer_request'), {
            'source_warehouse': 'WH1', 'destination_warehouse': 'WH2', 'file': xlsx(['Barcode No'], ['TR-BC-1']),
        })
        self.assertTrue(create.json()['success'])
        request_id = create.json()['request_id']
        receipt = self.client.post(reverse('receive_transfer_request', args=[request_id]), {
            'file': xlsx(['Barcode', 'Updated Location'], ['TR-BC-1', 'Rack 9']),
        })
        self.assertTrue(receipt.json()['success'])
        self.assertEqual(receipt.json()['pending'], 0)
        self.assertEqual(TransferRequest.objects.get(id=request_id).status, 'COMPLETED')
        self.assertEqual(Spare.objects.get(product=product).location, 'Rack 9')

    def test_transfer_request_page_shows_item_product_part_and_barcode(self):
        category = SpareCategory.objects.create(name='TRANSFER-SPARE-LIST')
        product = Product.objects.create(category=category, serial_no='TR-LIST-1', name='Listed transfer item')
        Spare.objects.create(product=product, part_no='LIST-PN-1', barcode='LIST-BC-1', location='Rack 1')
        transfer_request = TransferRequest.objects.create(
            source_warehouse='WH1',
            destination_warehouse='WH2',
            requested_by=self.user,
        )
        transfer_request.items.create(
            product=product,
            barcode='LIST-BC-1',
            source_location='Rack 1',
        )

        response = self.client.get(reverse('transfer_request_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Listed transfer item')
        self.assertContains(response, 'LIST-PN-1')
        self.assertContains(response, 'LIST-BC-1')
        self.assertContains(response, 'Approve one')
