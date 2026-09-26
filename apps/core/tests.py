from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from openpyxl import load_workbook

from apps.core.importers import HEADER_MAPS, IMPORT_LABELS, import_combined_stock_out_row
from apps.core.models import Product, RolePermission, UserProfile
from apps.core.permissions import has_permission
from apps.inventory.models import InventoryTransaction


class StockOutImportTests(TestCase):
    def test_every_category_has_a_stock_out_template(self):
        for base in ('battery', 'card', 'cpu', 'harddisk', 'memory',
                     'railkit', 'sfp', 'networking_spare', 'controller', 'server'):
            key = f'{base}_stock_out'
            self.assertIn(key, HEADER_MAPS, f'Missing stock-out template for {base}')
            self.assertIn(key, IMPORT_LABELS)
            base_headers = list(HEADER_MAPS[base].keys())
            combined_headers = list(HEADER_MAPS[key].keys())
            # Stock In columns must come first, unchanged and in order.
            self.assertEqual(combined_headers[:len(base_headers)], base_headers)
            # Appended Stock Out columns at the end.
            self.assertEqual(
                combined_headers[len(base_headers):],
                ['Client Name', 'Invoice No', 'OLF / DC No', 'Stock Status', 'Stock Out Date'],
            )

    def test_combined_card_stock_out_creates_product_stock_in_and_stock_out(self):
        row = {
            'brand': 'INTEL',
            'oem': 'OEM',
            'brand_model_no': 'X520',
            'interface': 'FC',
            'part_no': 'PN-1',
            'alt_part_no': '',
            'serial_no': 'CARD-SO-1',
            'brand_serial_no_1': 'CARD-SO-1',
            'capacity': '',
            'port': '',
            'barcode': 'BC-SO-1',
            'location': 'Rack 1',
            'reference_location': '',
            'remark': '',
            'store_location': 'WH1',
            'stock_status': 'LIVE',
            # appended stock-out columns:
            'so_client_name': 'Acme',
            'so_invoice_no': 'INV-9',
            'so_olf_dc_number': 'OLF-9',
            'so_stock_status': 'SALE',
            'so_stock_out_date': '2026-06-26',
        }
        product = import_combined_stock_out_row('card', row)
        self.assertIsInstance(product, Product)

        txns = InventoryTransaction.objects.filter(product=product).order_by('created_at')
        types = list(txns.values_list('transaction_type', flat=True))
        self.assertIn('IN', types)
        self.assertEqual(types[-1], 'OUT')

        out = txns.filter(transaction_type='OUT').latest('created_at')
        self.assertEqual(out.stock_status, 'SALE')
        self.assertEqual(out.client_name, 'Acme')
        self.assertEqual(out.invoice_no, 'INV-9')
        self.assertEqual(out.olf_dc_number, 'OLF-9')
        self.assertEqual(str(out.stock_out_date), '2026-06-26')


class RoleSettingsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='settings-admin', password='pass12345')
        UserProfile.objects.create(user=self.admin, role='ADMIN')
        self.stock_in = User.objects.create_user(username='settings-stock-in', password='pass12345')
        UserProfile.objects.create(user=self.stock_in, role='STOCK_IN')

    def test_custom_role_permissions_control_authorization(self):
        self.assertFalse(has_permission(self.stock_in, 'stock_out'))
        RolePermission.objects.create(role='STOCK_IN', permissions=['stock_in', 'stock_out'])
        self.assertTrue(has_permission(self.stock_in, 'stock_out'))

    def test_admin_can_save_role_permission_settings(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('role_permission_settings'), {
            'role': 'AUDIT', 'audit': 'on', 'audit_view': 'on',
        })
        self.assertRedirects(response, reverse('role_permission_settings'))
        self.assertEqual(RolePermission.objects.get(role='AUDIT').permissions, ['audit', 'audit_view'])


class DailyExportTests(TestCase):
    def test_daily_inventory_export_command_writes_both_workbooks(self):
        with TemporaryDirectory() as tmpdir:
            call_command('export_daily_inventory', output_dir=tmpdir, verbosity=0)
            export_root = Path(tmpdir) / 'exports' / date.today().isoformat()
            live_file = export_root / f'inventory-live-{date.today().isoformat()}.xlsx'
            sold_file = export_root / f'inventory-stocked_out-{date.today().isoformat()}.xlsx'

            self.assertTrue(live_file.exists())
            self.assertTrue(sold_file.exists())

            live_wb = load_workbook(live_file, read_only=True)
            sold_wb = load_workbook(sold_file, read_only=True)
            self.assertIn('Server', live_wb.sheetnames)
            self.assertIn('Server', sold_wb.sheetnames)
            live_wb.close()
            sold_wb.close()

    def test_daily_export_email_sends_both_workbooks(self):
        from django.core import mail
        from django.test import override_settings

        with TemporaryDirectory() as tmpdir:
            with override_settings(
                EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                DAILY_REPORT_RECIPIENTS=['abhiraj@zacocomputer.com'],
            ):
                call_command('export_daily_inventory', '--email',
                             output_dir=tmpdir, verbosity=0)
                self.assertEqual(len(mail.outbox), 1)
                message = mail.outbox[0]
                self.assertEqual(set(message.to), {'abhiraj@zacocomputer.com', 'nazim@zacocomputer.com'})
                names = sorted(attachment[0] for attachment in message.attachments)
                self.assertEqual(len(names), 2)
                self.assertTrue(all(n.endswith('.xlsx') for n in names))


# ── Daily report recipients, import-friendly export, failure e-mails ─────────
import tempfile
from io import BytesIO
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from openpyxl import Workbook

from apps.core.importers import REQUIRED_HEADERS, process_import_chunk, start_import_job
from apps.core.models import ReportRecipient
from apps.core.notifications import get_recipients
from apps.core.reporting import export_daily_inventory_snapshots, send_daily_inventory_email
from apps.servers.models import Server

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def _xlsx_upload(headers, rows, sheet='Sheet1', extra_sheet_first=False):
    wb = Workbook()
    ws = wb.active
    if extra_sheet_first:
        ws.title = 'Other'
        ws = wb.create_sheet(sheet)
    else:
        ws.title = sheet
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    return SimpleUploadedFile('data.xlsx', buf.getvalue())


def _row(headers, **values):
    return [values.get(h, '') for h in headers]


def _run_import(key, upload):
    job = start_import_job(key, upload, None)
    while job.status != 'DONE':
        job = process_import_chunk(job, chunk_size=100)
    return job


class ReportRecipientTests(TestCase):
    def test_default_recipients_seeded(self):
        self.assertEqual(
            set(get_recipients('DAILY_REPORT')),
            {'abhiraj@zacocomputer.com', 'nazim@zacocomputer.com'},
        )
        self.assertEqual(get_recipients('FAILURE_ALERT'), ['abhiraj@zacocomputer.com'])

    def test_recipients_are_configurable_and_inactive_ones_skipped(self):
        ReportRecipient.objects.filter(email='nazim@zacocomputer.com').update(is_active=False)
        ReportRecipient.objects.create(email='new@zacocomputer.com', kind='DAILY_REPORT')
        self.assertEqual(
            set(get_recipients('DAILY_REPORT')),
            {'abhiraj@zacocomputer.com', 'new@zacocomputer.com'},
        )

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_daily_email_goes_to_every_configured_recipient(self):
        with TemporaryDirectory() as tmp:
            result = send_daily_inventory_email(output_dir=tmp)
        self.assertTrue(result['sent'])
        self.assertEqual(
            set(mail.outbox[0].to),
            {'abhiraj@zacocomputer.com', 'nazim@zacocomputer.com'},
        )
        self.assertEqual(len(mail.outbox[0].attachments), 2)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_is_reported_as_not_sent(self):
        with TemporaryDirectory() as tmp:
            result = send_daily_inventory_email(output_dir=tmp)
        self.assertFalse(result['sent'])
        self.assertIn('SMTP is not configured', result['reason'])


@override_settings(EMAIL_BACKEND=LOCMEM)
class ExportImportRoundTripTests(TestCase):
    """The nightly workbooks must be re-importable as-is."""

    def setUp(self):
        override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        override.enable()
        self.addCleanup(override.disable)

    def _seed(self):
        mem_headers = list(HEADER_MAPS['memory'])
        _run_import('memory', _xlsx_upload(mem_headers, [
            _row(mem_headers, Brand='SAMSUNG', Model='M393', Size='16GB', **{
                'Serial No': 'MEM-LIVE-1', 'QTY': 1, 'Barcode': 'BC-1', 'Location': 'Rack 1'}),
            _row(mem_headers, Brand='SAMSUNG', Model='M393', Size='16GB', **{
                'Serial No': 'MEM-BAD-1', 'QTY': 1, 'Barcode': 'BC-2', 'Stock In Status': 'FAULTY'}),
        ]))

        so_headers = list(HEADER_MAPS['memory_stock_out'])
        _run_import('memory_stock_out', _xlsx_upload(so_headers, [
            _row(so_headers, Brand='HYNIX', Model='HMA', Size='8GB', **{
                'Serial No': 'MEM-SOLD-1', 'QTY': 1, 'Barcode': 'BC-3', 'Client Name': 'Acme',
                'Invoice No': 'INV-1', 'OLF / DC No': 'DC-1', 'Stock Status': 'SALE',
                'Stock Out Date': '2026-06-26'}),
        ]))

        srv_headers = list(HEADER_MAPS['server'])

        def srv(spare, serial, part='', parent=''):
            return _row(srv_headers, **{
                'Testing Date': '2026-06-01', 'Tested by/FE name': 'SAMIR',
                'Machine Type': 'RACK SERVER', 'Machine no': 'M-1',
                'System Service Tag No': 'TAG123', 'Model': 'R630', 'Spares Type': spare,
                'Part No': part, 'Serial No': serial, 'QTY': 1,
                'Working/Not working': 'WORKING', 'Location': 'Rack 2',
                'Parent-child Location': parent})
        _run_import('server', _xlsx_upload(srv_headers, [
            srv('CABINET', 'TAG123'),
            srv('MOTHER BOARD', 'MB-1', 'PN-MB', 'TAG123'),
            srv('MEMORY', 'SRV-MEM-1', 'PN-MEM', 'TAG123'),
        ]))

    def test_export_headers_match_import_templates(self):
        self._seed()
        with TemporaryDirectory() as tmp:
            outputs = export_daily_inventory_snapshots(output_dir=tmp)
            live = load_workbook(outputs['live'], read_only=True)
            sold = load_workbook(outputs['stocked_out'], read_only=True)

            def headers_of(wb, key):
                return [c.value for c in next(wb[IMPORT_LABELS[key]].iter_rows(max_row=1))]

            for key in ('battery', 'card', 'cpu', 'harddisk', 'memory',
                        'networking_spare', 'railkit', 'sfp'):
                self.assertEqual(headers_of(live, key), list(HEADER_MAPS[key]))
                self.assertEqual(headers_of(sold, key), list(HEADER_MAPS[f'{key}_stock_out']))
            for wb, suffix in ((live, ''), (sold, '_stock_out')):
                for key in ('controller', 'server'):
                    missing = REQUIRED_HEADERS[key + suffix] - set(headers_of(wb, key))
                    self.assertFalse(missing, f'{key}{suffix} missing {missing}')
            live.close()
            sold.close()

    def test_exported_files_reimport_cleanly_after_data_is_wiped(self):
        self._seed()
        with TemporaryDirectory() as tmp:
            outputs = export_daily_inventory_snapshots(output_dir=tmp)
            live_bytes = Path(outputs['live']).read_bytes()
            sold_bytes = Path(outputs['stocked_out']).read_bytes()

        InventoryTransaction.objects.all().delete()
        Server.objects.all().delete()
        Product.objects.all().delete()
        self.assertEqual(Product.objects.count(), 0)

        # The SAME file is uploaded for every category; the matching sheet is read.
        for key, data in (('memory', live_bytes), ('server', live_bytes),
                          ('memory_stock_out', sold_bytes)):
            job = _run_import(key, SimpleUploadedFile('same.xlsx', data))
            self.assertEqual(job.error_count, 0, f'{key}: {job.errors}')
            self.assertGreater(job.success_count, 0, key)
        self.assertEqual(len(mail.outbox), 0)  # no failure mail on a clean import

        sold = InventoryTransaction.objects.filter(
            product__serial_no='MEM-SOLD-1').order_by('-created_at').first()
        self.assertEqual((sold.transaction_type, sold.client_name), ('OUT', 'Acme'))
        bad = InventoryTransaction.objects.filter(
            product__serial_no='MEM-BAD-1').order_by('-created_at').first()
        self.assertEqual(bad.stock_status, 'FAULTY')
        self.assertTrue(Product.objects.filter(serial_no='MEM-LIVE-1').exists())
        self.assertEqual(Server.objects.get(service_tag='TAG123').components.count(), 3)

    def test_multi_sheet_workbook_reads_sheet_matching_category(self):
        headers = list(HEADER_MAPS['memory'])
        up = _xlsx_upload(headers, [_row(headers, Brand='SAMSUNG')],
                          sheet='Memory', extra_sheet_first=True)
        self.assertEqual(start_import_job('memory', up, None).total_rows, 1)


@override_settings(EMAIL_BACKEND=LOCMEM)
class FailureEmailTests(TestCase):
    def setUp(self):
        override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        override.enable()
        self.addCleanup(override.disable)

    def test_missing_columns_mails_reason(self):
        with self.assertRaises(ValueError):
            start_import_job('memory', _xlsx_upload(['Wrong'], [['x']]), None)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['abhiraj@zacocomputer.com'])
        self.assertIn('Missing columns', mail.outbox[0].body)

    def test_row_errors_mail_row_numbers_and_reason(self):
        headers = list(HEADER_MAPS['server'])
        job = _run_import('server', _xlsx_upload(headers, [_row(headers, Model='R630')]))
        self.assertEqual(job.error_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['abhiraj@zacocomputer.com'])
        self.assertIn('Row 2', mail.outbox[0].body)
        self.assertIn('Service Tag', mail.outbox[0].body)

    def test_clean_import_sends_no_mail(self):
        headers = list(HEADER_MAPS['memory'])
        _run_import('memory', _xlsx_upload(headers, [_row(headers, Brand='SAMSUNG')]))
        self.assertEqual(len(mail.outbox), 0)

    def test_nightly_command_failure_mails_alert_and_reraises(self):
        with mock.patch('apps.core.management.commands.export_daily_inventory.send_daily_inventory_email',
                        side_effect=RuntimeError('SMTP down')):
            with self.assertRaises(RuntimeError):
                call_command('export_daily_inventory', '--email', verbosity=0)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('SMTP down', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['abhiraj@zacocomputer.com'])


class RolePermissionUiTests(TestCase):
    """Buttons / menu items must follow the saved Role Settings, not role names."""

    def setUp(self):
        self.user = User.objects.create_user(username='ui-stock-in', password='pass12345')
        UserProfile.objects.create(user=self.user, role='STOCK_IN')
        self.client.force_login(self.user)

    def _page(self):
        return self.client.get(reverse('server_list')).content.decode()

    def test_granting_stock_out_to_stock_in_role_shows_stock_out_button_flag(self):
        self.assertIn('const canStockOut = false;', self._page())
        RolePermission.objects.create(role='STOCK_IN', permissions=['stock_in', 'stock_out'])
        self.assertIn('const canStockOut = true;', self._page())

    def test_revoking_permission_hides_flag_and_menu_items(self):
        page = self._page()
        self.assertIn('const canMap = true;', page)
        self.assertIn(reverse('add_server'), page)
        self.assertIn(reverse('sales_return_history'), page)
        RolePermission.objects.create(role='STOCK_IN', permissions=['audit_view'])
        page = self._page()
        self.assertIn('const canMap = false;', page)
        self.assertNotIn(reverse('add_server'), page)
        self.assertNotIn(reverse('sales_return_history'), page)
        self.assertIn(reverse('audit_report'), page)

    def test_admin_role_customisation_is_honoured_but_keeps_user_management(self):
        admin = User.objects.create_user(username='ui-admin', password='pass12345', is_superuser=True)
        UserProfile.objects.create(user=admin, role='ADMIN')
        RolePermission.objects.create(role='ADMIN', permissions=['stock_in'])
        self.assertTrue(has_permission(admin, 'stock_in'))
        self.assertTrue(has_permission(admin, 'user_management'))
        self.assertFalse(has_permission(admin, 'stock_out'))


class ListFilterTests(TestCase):
    """Status / store / brand / date filters behave the same on every list."""

    def setUp(self):
        from apps.categories.models import Card
        from apps.core.models import Brand, SpareCategory
        self.user = User.objects.create_superuser(username='flt', password='pass12345', email='f@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        cat = SpareCategory.objects.create(name='CARD')
        self.dell = Brand.objects.create(name='DELL')
        self.hp = Brand.objects.create(name='HP')

        def card(serial, brand, status, store, out=False, out_status='SALE', out_date=None):
            p = Product.objects.create(category=cat, serial_no=serial, name=serial)
            Card.objects.create(product=p, brand=brand, brand_serial_no_1=serial)
            InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location=store, stock_status=status)
            if out:
                InventoryTransaction.objects.create(
                    product=p, transaction_type='OUT', store_location=store,
                    stock_status=out_status, stock_out_date=out_date)
            return p
        card('C-LIVE-DELL-WH1', self.dell, 'LIVE', 'WH1')
        card('C-FAULTY-DELL-WH2', self.dell, 'FAULTY', 'WH2')
        card('C-FAULTY-HP-WH1', self.hp, 'FAULTY', 'WH1')
        card('C-SCRAP-HP-WH2', self.hp, 'SCRAP', 'WH2')
        card('C-SOLD-1', self.dell, 'LIVE', 'WH1', out=True, out_status='SALE', out_date='2026-01-10')
        card('C-SOLD-2', self.dell, 'LIVE', 'WH1', out=True, out_status='RENT', out_date='2026-03-10')

    def serials(self, url, **params):
        res = self.client.get(url, params)
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        return {s for s in ('C-LIVE-DELL-WH1', 'C-FAULTY-DELL-WH2', 'C-FAULTY-HP-WH1', 'C-SCRAP-HP-WH2',
                            'C-SOLD-1', 'C-SOLD-2') if s in html}

    def test_live_list_filters_and_combinations(self):
        url = reverse('card_list')
        self.assertEqual(len(self.serials(url)), 4)  # sold cards never show in the live list
        self.assertEqual(self.serials(url, status='FAULTY'), {'C-FAULTY-DELL-WH2', 'C-FAULTY-HP-WH1'})
        self.assertEqual(self.serials(url, store='WH2'), {'C-FAULTY-DELL-WH2', 'C-SCRAP-HP-WH2'})
        self.assertEqual(self.serials(url, brand=self.hp.pk), {'C-FAULTY-HP-WH1', 'C-SCRAP-HP-WH2'})
        self.assertEqual(self.serials(url, status='FAULTY', store='WH2'), {'C-FAULTY-DELL-WH2'})
        self.assertEqual(self.serials(url, status='SCRAP', brand=self.dell.pk), set())
        self.assertEqual(self.serials(url, q='SCRAP'), {'C-SCRAP-HP-WH2'})
        self.assertEqual(self.serials(url, q='FAULTY', store='WH1'), {'C-FAULTY-HP-WH1'})

    def test_invalid_filter_values_are_ignored_not_errors(self):
        url = reverse('card_list')
        self.assertEqual(len(self.serials(url, status='NOPE', store='XX', brand='abc', date_from='garbage')), 4)

    def test_sold_list_status_and_date_filters(self):
        url = reverse('inventory_sold', args=['card'])
        self.assertEqual(self.serials(url), {'C-SOLD-1'})                      # opens on SALE
        self.assertEqual(self.serials(url, status=''), {'C-SOLD-1', 'C-SOLD-2'})  # "All statuses"
        self.assertEqual(self.serials(url, status='RENT'), {'C-SOLD-2'})
        self.assertEqual(self.serials(url, status='', date_from='2026-02-01'), {'C-SOLD-2'})
        self.assertEqual(self.serials(url, status='', date_to='2026-02-01'), {'C-SOLD-1'})
        self.assertEqual(self.serials(url, status='', date_from='2026-01-01', date_to='2026-12-31'),
                         {'C-SOLD-1', 'C-SOLD-2'})

    def test_faulty_list_only_faulty_and_damaged_with_filters(self):
        url = reverse('inventory_faulty', args=['card'])
        self.assertEqual(self.serials(url), {'C-FAULTY-DELL-WH2', 'C-FAULTY-HP-WH1'})
        self.assertEqual(self.serials(url, store='WH1'), {'C-FAULTY-HP-WH1'})
        self.assertEqual(self.serials(url, status='SCRAP'), {'C-FAULTY-DELL-WH2', 'C-FAULTY-HP-WH1'})  # invalid here -> ignored

    def test_pagination_links_keep_filters(self):
        from apps.categories.models import Card
        from apps.core.models import SpareCategory
        cat = SpareCategory.objects.get(name='CARD')
        for i in range(60):
            p = Product.objects.create(category=cat, serial_no=f'BULK-{i}', name=f'BULK-{i}')
            Card.objects.create(product=p, brand=self.dell, brand_serial_no_1=f'BULK-{i}')
            InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH3', stock_status='TESTING')
        html = self.client.get(reverse('card_list'), {'status': 'TESTING', 'store': 'WH3'}).content.decode()
        self.assertIn('status=TESTING', html)
        self.assertIn('page=2', html)
        page2 = self.client.get(reverse('card_list'), {'status': 'TESTING', 'store': 'WH3', 'page': 2})
        self.assertEqual(page2.context['total_count'], 60)
        self.assertEqual(len(page2.context['cards']), 10)

    def test_every_list_page_renders_with_filters(self):
        for name, args in (('spare_list', []), ('cpu_list', []), ('memory_list', []), ('sfp_list', []),
                           ('railkit_list', []), ('harddisk_list', []), ('controller_list', []),
                           ('networking_spare_list', []), ('server_list', []), ('server_empty_list', []),
                           ('server_out_list', []), ('server_faulty_list', []), ('spare_out_report', []),
                           ('frozen_inventory_list', []), ('inventory_sold', ['memory']),
                           ('inventory_faulty', ['sfp']), ('stock_out_status_list', ['TESTING'])):
            for params in ({}, {'status': 'FAULTY', 'store': 'WH1', 'q': 'x', 'date_from': '2026-01-01'}):
                res = self.client.get(reverse(name, args=args), params)
                self.assertEqual(res.status_code, 200, f'{name} {params}')


class LegendFilterTests(ListFilterTests):
    """The topbar colour legend chips act as one-click filters."""

    def chip_href(self, html, label):
        import re
        m = re.search(r'<a class="legend-item[^"]*"(?: href="([^"]*)")?\s+title="[^"]*"><i class="legend-swatch"[^>]*></i>%s</a>' % label, html)
        self.assertIsNotNone(m, label)
        return m.group(1) or ''

    def test_chips_link_to_status_filter_on_supporting_lists(self):
        html = self.client.get(reverse('card_list')).content.decode()
        self.assertIn('status=FAULTY', self.chip_href(html, 'Faulty'))
        self.assertIn('status=SCRAP', self.chip_href(html, 'Scrap'))

    def test_active_chip_clears_and_keeps_other_filters(self):
        html = self.client.get(reverse('card_list'), {'status': 'FAULTY', 'store': 'WH1'}).content.decode()
        href = self.chip_href(html, 'Faulty')
        self.assertIn('status=&', href + '&')
        self.assertIn('store=WH1', href)
        self.assertNotIn('status=FAULTY', href)
        self.assertIn('status=DAMAGED', self.chip_href(html, 'Damaged'))
        self.assertIn('store=WH1', self.chip_href(html, 'Damaged'))

    def test_chip_disabled_when_page_cannot_filter_it(self):
        html = self.client.get(reverse('inventory_faulty', args=['card'])).content.decode()
        self.assertTrue(self.chip_href(html, 'Faulty'))
        self.assertEqual(self.chip_href(html, 'Scrap'), '')

    def test_empty_chip_switches_server_tabs(self):
        html = self.client.get(reverse('server_list'), {'q': 'r630'}).content.decode()
        href = self.chip_href(html, 'Empty')
        self.assertTrue(href.startswith(reverse('server_empty_list')))
        self.assertIn('q=r630', href)
        html = self.client.get(reverse('server_empty_list')).content.decode()
        self.assertTrue(self.chip_href(html, 'Empty').startswith(reverse('server_list')))

    def test_chip_filter_actually_filters(self):
        res = self.client.get(reverse('card_list'), {'status': 'SCRAP'})
        self.assertEqual(self.serials(reverse('card_list'), status='SCRAP'), {'C-SCRAP-HP-WH2'})
