from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from openpyxl import load_workbook

from apps.core.importers import HEADER_MAPS, IMPORT_LABELS, import_combined_stock_out_row
from apps.core.models import Product, RolePermission, SpareCategory, UserProfile
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
        self.assertRedirects(response, reverse('role_permission_settings') + '?open=AUDIT')
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
                # Sent as two separate emails (live, stocked-out) so one large
                # attachment timing out doesn't take the other down with it.
                self.assertEqual(len(mail.outbox), 2)
                for message in mail.outbox:
                    self.assertEqual(set(message.to), {'abhiraj@zacocomputer.com', 'nazim@zacocomputer.com'})
                    self.assertEqual(len(message.attachments), 1)
                    self.assertTrue(message.attachments[0][0].endswith('.xlsx'))
                subjects = {m.subject for m in mail.outbox}
                self.assertTrue(any('Live' in s for s in subjects))
                self.assertTrue(any('Stocked Out' in s for s in subjects))


# ── Daily report recipients, import-friendly export, failure e-mails ─────────
import tempfile
from io import BytesIO
from unittest import mock

from django.core.mail import EmailMessage

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
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            set(mail.outbox[0].to),
            {'abhiraj@zacocomputer.com', 'nazim@zacocomputer.com'},
        )
        self.assertEqual(len(mail.outbox[0].attachments), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_backend_is_reported_as_not_sent(self):
        with TemporaryDirectory() as tmp:
            result = send_daily_inventory_email(output_dir=tmp)
        self.assertFalse(result['sent'])
        self.assertIn('SMTP is not configured', result['reason'])


class DailyEmailRetryTests(TestCase):
    """A dropped/timed-out SMTP connection (the exact failure from the
    production incident: SMTPServerDisconnected mid-send of a large
    attachment) is retried with a fresh connection instead of failing the
    whole nightly job outright."""

    def setUp(self):
        override = override_settings(EMAIL_BACKEND=LOCMEM)
        override.enable()
        self.addCleanup(override.disable)
        self._sleep_patch = mock.patch('apps.core.reporting.time.sleep')
        self._sleep_patch.start()
        self.addCleanup(self._sleep_patch.stop)

    def test_transient_smtp_disconnect_is_retried_and_succeeds(self):
        from smtplib import SMTPServerDisconnected
        real_send = EmailMessage.send
        calls = {'n': 0}

        def flaky_send(self, *a, **k):
            calls['n'] += 1
            if calls['n'] == 1:
                raise SMTPServerDisconnected('Server not connected')
            return real_send(self, *a, **k)

        with mock.patch.object(EmailMessage, 'send', flaky_send):
            with TemporaryDirectory() as tmp:
                result = send_daily_inventory_email(output_dir=tmp)
        self.assertTrue(result['sent'])
        self.assertNotIn('partial_failure', result)
        self.assertGreaterEqual(calls['n'], 3)  # 2 reports, one retried once

    def test_persistent_failure_on_one_report_is_a_partial_success(self):
        from smtplib import SMTPServerDisconnected
        real_send = EmailMessage.send

        def always_fail_live_only(self, *a, **k):
            if 'Live' in self.subject:
                raise SMTPServerDisconnected('Server not connected')
            return real_send(self, *a, **k)

        with mock.patch.object(EmailMessage, 'send', always_fail_live_only):
            with TemporaryDirectory() as tmp:
                result = send_daily_inventory_email(output_dir=tmp)
        self.assertTrue(result['sent'])  # the stocked-out report still went out
        self.assertIn('live', result['partial_failure'])

    def test_all_reports_failing_raises_so_the_job_alerts_and_exits_nonzero(self):
        with mock.patch.object(EmailMessage, 'send', side_effect=TimeoutError('timed out')):
            with TemporaryDirectory() as tmp:
                with self.assertRaises(RuntimeError):
                    send_daily_inventory_email(output_dir=tmp)

    def test_partial_failure_via_command_sends_alert_but_does_not_raise(self):
        from smtplib import SMTPServerDisconnected
        real_send = EmailMessage.send

        def always_fail_live_only(self, *a, **k):
            if 'Live' in self.subject:
                raise SMTPServerDisconnected('Server not connected')
            return real_send(self, *a, **k)

        with mock.patch.object(EmailMessage, 'send', always_fail_live_only):
            with TemporaryDirectory() as tmp:
                call_command('export_daily_inventory', '--email', output_dir=tmp, verbosity=0)
        # One alert for the failed "live" report, plus the successful "stocked_out" report email.
        alert = next(m for m in mail.outbox if 'partially sent' in m.subject)
        self.assertIn('live', alert.body)
        self.assertEqual(alert.to, ['abhiraj@zacocomputer.com'])


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
        return self.client.get(reverse('dashboard')).content.decode()

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


@override_settings(EMAIL_BACKEND=LOCMEM)
class ServerHardDiskImportTests(TestCase):
    def test_hard_disk_row_keeps_machine_model(self):
        from apps.categories.models import HardDisk
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            headers = list(HEADER_MAPS['server'])

            def row(spare, serial, parent=''):
                return _row(headers, **{
                    'Machine Type': 'STORAGE', 'System Service Tag No': 'ST1', 'Model': 'IBM V7000',
                    'Spares Type': spare, 'Serial No': serial, 'QTY': 1, 'Parent-child Location': parent})
            job = _run_import('server', _xlsx_upload(headers, [row('CABINET', 'ST1'), row('HARD DISK', 'HDD-1', 'ST1')]))
        self.assertEqual(job.error_count, 0, job.errors)
        self.assertEqual(HardDisk.objects.get(product__serial_no='HDD-1').model, 'IBM V7000')


class InstalledInTests(TestCase):
    def setUp(self):
        from apps.categories.models import Card
        from apps.core.models import SpareCategory
        from apps.servers.models import Server, ServerComponent
        self.user = User.objects.create_superuser(username='inst', password='pass12345', email='i@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        cat = SpareCategory.objects.create(name='CARD')
        cab = SpareCategory.objects.create(name='CABINET')

        def card(serial):
            p = Product.objects.create(category=cat, serial_no=serial, name=serial)
            Card.objects.create(product=p, brand_serial_no_1=serial)
            InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')
            return p
        self.loose = card('LOOSE-1')
        self.inside = card('INSIDE-1')
        self.sold_inside = card('SOLD-INSIDE-1')
        cabinet = Product.objects.create(category=cab, serial_no='SRV-CAB', name='cab')
        self.server = Server.objects.create(service_tag='TAG9', model='R630', machine_no='M-9', product=cabinet)
        ServerComponent.objects.create(server=self.server, product=self.inside, spare_type='CARD', serial_no='INSIDE-1')
        ServerComponent.objects.create(server=self.server, product=self.sold_inside, spare_type='CARD', serial_no='SOLD-INSIDE-1')
        InventoryTransaction.objects.create(product=self.sold_inside, transaction_type='OUT', store_location='WH1', stock_status='SALE')

    def test_bulk_lookup_returns_only_installed_products(self):
        ids = f'{self.loose.id},{self.inside.id},{self.sold_inside.id},abc,'
        data = self.client.get(reverse('installed_in'), {'ids': ids}).json()
        self.assertNotIn(str(self.loose.id), data)
        info = data[str(self.inside.id)]
        self.assertEqual((info['type'], info['out']), ('server', False))
        self.assertIn('TAG9', info['label'])
        self.assertTrue(data[str(self.sold_inside.id)]['out'])
        self.assertEqual(self.client.get(reverse('installed_in')).json(), {})

    def test_controller_membership(self):
        from apps.categories.models import Controller, Spare
        from apps.core.models import SpareCategory
        cp = Product.objects.create(category=SpareCategory.objects.get(name='CARD'), serial_no='CTRL-1', name='ctrl')
        ctrl = Controller.objects.create(product=cp, model='P440')
        sp = Product.objects.create(category=SpareCategory.objects.get(name='CARD'), serial_no='BAT-1', name='bat')
        Spare.objects.create(product=sp, controller=ctrl)
        data = self.client.get(reverse('installed_in'), {'ids': str(sp.id)}).json()
        self.assertEqual(data[str(sp.id)]['type'], 'controller')
        self.assertIn('P440', data[str(sp.id)]['label'])

    def test_installed_filter_on_lists(self):
        url = reverse('card_list')
        def found(**p):
            html = self.client.get(url, p).content.decode()
            return {s for s in ('LOOSE-1', 'INSIDE-1') if s in html}
        self.assertEqual(found(), {'LOOSE-1', 'INSIDE-1'})
        self.assertEqual(found(installed='yes'), {'INSIDE-1'})
        self.assertEqual(found(installed='no'), {'LOOSE-1'})
        self.assertEqual(found(installed='garbage'), {'LOOSE-1', 'INSIDE-1'})

    def test_pages_ship_the_installed_in_hooks(self):
        html = self.client.get(reverse('card_list')).content.decode()
        self.assertIn('/inventory/installed-in/', html)
        self.assertIn('installed-in-notice', html)
        self.assertIn('Installed</a>', html)


@override_settings(EMAIL_BACKEND=LOCMEM)
class BarcodeStockOutImportTests(TestCase):
    """The plain "Stock Out" import: 6 columns, barcode only, any category."""

    HEADERS = ['Barcode No', 'Client Name', 'Invoice No', 'OLF / DC No', 'Stock Status', 'Stock Out Date']

    def setUp(self):
        from apps.categories.models import Card, Controller, HardDisk, Memory
        from apps.core.models import SpareCategory
        override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        override.enable()
        self.addCleanup(override.disable)
        cat = SpareCategory.objects.create(name='MIXED')

        def prod(serial, store='WH2'):
            p = Product.objects.create(category=cat, serial_no=serial, name=serial)
            InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location=store, stock_status='LIVE')
            return p
        self.card = prod('S-CARD'); Card.objects.create(product=self.card, barcode='BC-CARD')
        self.mem = prod('S-MEM'); Memory.objects.create(product=self.mem, barcode='BC-MEM')
        self.hdd = prod('S-HDD'); HardDisk.objects.create(product=self.hdd, barcode='BC-HDD', tray_barcode='TRAY-1')
        self.ctrl = prod('S-CTRL'); Controller.objects.create(product=self.ctrl, model='P440', barcode='BC-CTRL')

    def run_rows(self, rows):
        return _run_import('stock_out', _xlsx_upload(self.HEADERS, rows))

    def latest(self, product):
        return product.transactions.order_by('-created_at', '-id').first()

    def test_template_has_exactly_the_six_columns(self):
        self.assertEqual(list(HEADER_MAPS['stock_out']), self.HEADERS)

    def test_stocks_out_by_barcode_in_any_category_and_reports_missing(self):
        job = self.run_rows([
            ['BC-CARD', 'Acme', 'INV-1', 'DC-1', 'SALE', '2026-06-26'],
            ['bc-mem', 'Beta', 'INV-2', 'DC-2', 'RENT', '26/06/2026'],
            ['NOPE-1', 'X', '', '', 'SALE', ''],
            ['TRAY-1', 'Gamma', 'INV-3', '', 'SALE', ''],
            ['BC-CTRL', 'Delta', '', '', '', ''],
            ['NOPE-2', '', '', '', '', ''],
        ])
        self.assertEqual((job.success_count, job.error_count), (4, 2))
        errors = ' | '.join(e['error'] for e in job.errors)
        self.assertIn('Barcode "NOPE-1" not found', errors)
        self.assertIn('Barcode "NOPE-2" not found', errors)
        self.assertEqual([e['row'] for e in job.errors], [4, 7])
        card = self.latest(self.card)
        self.assertEqual((card.transaction_type, card.client_name, card.invoice_no, card.olf_dc_number, card.stock_status),
                         ('OUT', 'Acme', 'INV-1', 'DC-1', 'SALE'))
        self.assertEqual(str(card.stock_out_date), '2026-06-26')
        self.assertEqual(card.store_location, 'WH1')          # the warehouse chosen on the import page
        mem = self.latest(self.mem)
        self.assertEqual((mem.stock_status, str(mem.stock_out_date)), ('RENT', '2026-06-26'))
        self.assertEqual(self.latest(self.hdd).transaction_type, 'OUT')
        ctrl = self.latest(self.ctrl)
        self.assertEqual((ctrl.transaction_type, ctrl.stock_status), ('OUT', 'SALE'))   # blank status -> SALE
        # the failure mail names the barcodes
        self.assertIn('NOPE-1', mail.outbox[0].body)

    def test_already_stocked_out_and_bad_date_are_row_errors(self):
        job = self.run_rows([
            ['BC-CARD', 'Acme', '', '', 'SALE', ''],
            ['BC-CARD', 'Acme', '', '', 'SALE', ''],
            ['BC-MEM', 'Acme', '', '', 'SALE', 'not-a-date'],
        ])
        self.assertEqual((job.success_count, job.error_count), (1, 2))
        text = ' | '.join(e['error'] for e in job.errors)
        self.assertIn('already stocked out', text)
        self.assertIn('Invalid Stock Out Date', text)
        self.assertEqual(self.latest(self.mem).transaction_type, 'IN')

    def test_barcode_column_is_required_others_optional(self):
        with self.assertRaises(ValueError):
            start_import_job('stock_out', _xlsx_upload(['Client Name'], [['x']]), None)
        job = _run_import('stock_out', _xlsx_upload(['Barcode No', 'Client Name'], [['BC-CARD', 'x']]))
        self.assertEqual((job.success_count, job.error_count), (1, 0))


class StockOutTemplateDownloadTests(TestCase):
    def test_stock_out_templates_start_with_barcode_no(self):
        user = User.objects.create_superuser(username='tpl', password='pass12345', email='t@example.com')
        UserProfile.objects.create(user=user, role='ADMIN')
        self.client.force_login(user)
        expected = ['Barcode No', 'Client Name', 'Invoice No', 'OLF / DC No', 'Stock Status', 'Stock Out Date']
        for key in ('stock_out_columns', 'stock_out'):
            res = self.client.get(reverse('inventory_import_template', args=[key]))
            ws = load_workbook(BytesIO(res.content)).active
            self.assertEqual([c.value for c in ws[1]], expected, key)


# ---- Spare sub-categories split + dashboard cards ----
from apps.categories.spare_subcategories import SPARE_SUBCATEGORIES, spare_kind_key, spare_subcategory_q
from apps.core.dashboard_stats import card_data, dashboard_registry, kind_overview


class SpareSubcategoryPartitionTests(TestCase):
    """Every SpareCategory name variant lands in exactly one sub-category --
    the whole point of the split."""

    def _spare(self, category_name, barcode):
        cat = SpareCategory.objects.get_or_create(name=category_name)[0]
        p = Product.objects.create(category=cat, serial_no=barcode, name=barcode)
        from apps.categories.models import Spare
        Spare.objects.create(product=p, barcode=barcode)
        InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')
        return p

    def test_known_spellings_and_typos_map_to_the_right_subcategory(self):
        cases = [
            ('CABLE', 'cable'), ('FIBER CABLE', 'cable'),
            ('BATTERY', 'battery'),
            ('COOLING FAN', 'cooling_fan'), ('COOILING FAN', 'cooling_fan'), ('COOLINGFAN', 'cooling_fan'),
            ('POWER SUPPLY', 'power_supply'), ('POWERSUPPLY', 'power_supply'),
            ('IO BOARD', 'io_board'), ('PASSTHRU CARD', 'io_board'), ('PROCESSOR BOARD', 'io_board'),
            ('MOTHER BOARD', 'motherboard'),
            ('SOME RANDOM THING NOBODY LISTED', 'miscellaneous'),
        ]
        for i, (cat_name, expected_slug) in enumerate(cases):
            p = self._spare(cat_name, f'BC-{i}')
            for slug in SPARE_SUBCATEGORIES:
                from apps.categories.models import Spare
                matched = Spare.objects.filter(spare_subcategory_q(slug), product=p).exists()
                self.assertEqual(matched, slug == expected_slug, f'{cat_name} vs {slug}')

    def test_every_subcategory_is_mutually_exclusive_and_exhaustive(self):
        from apps.categories.models import Spare
        names = ['CABLE', 'BATTERY', 'MOTHER BOARD', 'RANDOM ONE', 'RANDOM TWO', 'VRM', 'HEAT SINK']
        for i, name in enumerate(names):
            self._spare(name, f'EX-{i}')
        total = Spare.objects.count()
        counted = 0
        seen_ids = set()
        for slug in SPARE_SUBCATEGORIES:
            ids = set(Spare.objects.filter(spare_subcategory_q(slug)).values_list('id', flat=True))
            self.assertFalse(ids & seen_ids, f'{slug} overlaps a previous sub-category')
            seen_ids |= ids
            counted += len(ids)
        self.assertEqual(counted, total)
        self.assertEqual(len(seen_ids), total)


@override_settings(EMAIL_BACKEND=LOCMEM)
class SpareSubcategoryImportTests(TestCase):
    HEADERS = ['Brand', 'Model', 'Part No', 'Alt Part No', 'Serial No', 'Alt Serial. no',
               'Specs', 'QTY', 'Barcode No', 'Location', 'Reference Location', 'Remark(describe exact issue)']

    def setUp(self):
        override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        override.enable()
        self.addCleanup(override.disable)

    def test_stock_in_forces_the_canonical_category_no_product_column_needed(self):
        from apps.categories.models import Spare
        job = _run_import('spare_motherboard', _xlsx_upload(self.HEADERS, [
            _row(self.HEADERS, Brand='DELL', **{'Serial No': 'MB-SN-1', 'Barcode No': 'MB-BC-1'}),
        ]))
        self.assertEqual((job.success_count, job.error_count), (1, 0))
        spare = Spare.objects.get(barcode='MB-BC-1')
        self.assertEqual(spare.product.category.name, 'MOTHER BOARD')

    def test_miscellaneous_import_keeps_each_rows_own_product_as_its_category(self):
        from apps.categories.models import Spare
        headers = ['Product'] + self.HEADERS
        job = _run_import('spare_miscellaneous', _xlsx_upload(headers, [
            _row(headers, Product='FRONT BEZEL', Brand='DELL', **{'Serial No': 'MISC-SN-1', 'Barcode No': 'MISC-BC-1'}),
            _row(headers, Product='CARTRIDGE', Brand='HP', **{'Serial No': 'MISC-SN-2', 'Barcode No': 'MISC-BC-2'}),
            _row(headers, Product='', Brand='', **{'Serial No': 'MISC-SN-3', 'Barcode No': 'MISC-BC-3'}),
        ]))
        self.assertEqual((job.success_count, job.error_count), (3, 0), job.errors)
        self.assertEqual(Spare.objects.get(barcode='MISC-BC-1').product.category.name, 'FRONT BEZEL')
        self.assertEqual(Spare.objects.get(barcode='MISC-BC-2').product.category.name, 'CARTRIDGE')
        self.assertEqual(Spare.objects.get(barcode='MISC-BC-3').product.category.name, 'MISCELLANEOUS')

    def test_case_insensitive_headers_from_real_world_files_are_accepted(self):
        messy_headers = ['Brand', 'Model', 'Part no', 'Alt part no', 'Serial no', 'Alt serial. no',
                         'Specs', 'Qty', 'Barcode no', 'Location', 'Reference location', 'Remark(describe exact issue)']
        job = _run_import('spare_power_supply', _xlsx_upload(messy_headers, [
            _row(messy_headers, Brand='HP', **{'Serial no': 'PS-1', 'Barcode no': 'PS-BC-1', 'Qty': 2}),
        ]))
        self.assertEqual((job.success_count, job.error_count), (1, 0), job.errors)

    def test_combined_stock_out_variant_is_generated_and_works(self):
        headers = list(HEADER_MAPS['spare_vrm_stock_out'])
        self.assertIn('Client Name', headers)
        job = _run_import('spare_vrm_stock_out', _xlsx_upload(headers, [
            _row(headers, Brand='DELL', **{
                'Serial No': 'VRM-1', 'Barcode No': 'VRM-BC-1',
                'Client Name': 'Acme', 'Stock Status': 'SALE',
            }),
        ]))
        self.assertEqual((job.success_count, job.error_count), (1, 0), job.errors)
        txn = InventoryTransaction.objects.filter(product__serial_no='VRM-1').order_by('-created_at').first()
        self.assertEqual((txn.transaction_type, txn.client_name), ('OUT', 'Acme'))

    def test_import_page_lists_all_19_categories(self):
        for slug, cfg in SPARE_SUBCATEGORIES.items():
            key = spare_kind_key(slug)
            self.assertIn(key, IMPORT_LABELS)
            self.assertEqual(IMPORT_LABELS[key], cfg['label'])
            self.assertIn(f'{key}_stock_out', IMPORT_LABELS)


class SpareSubcategoryRoutingTests(TestCase):
    """Live/sold/faulty pages for one sub-category never leak another's rows."""

    def setUp(self):
        self.user = User.objects.create_superuser(username='subcat', password='pass12345', email='s@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        from apps.categories.models import Spare

        def spare(cat_name, serial, out=False):
            cat = SpareCategory.objects.get_or_create(name=cat_name)[0]
            p = Product.objects.create(category=cat, serial_no=serial, name=serial)
            Spare.objects.create(product=p, barcode=serial)
            InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')
            if out:
                InventoryTransaction.objects.create(product=p, transaction_type='OUT', store_location='WH1', stock_status='SALE')
            return p
        self.cable = spare('CABLE', 'ROUTE-CABLE-1')
        self.battery = spare('BATTERY', 'ROUTE-BATTERY-1')
        self.sold_cable = spare('CABLE', 'ROUTE-CABLE-SOLD', out=True)

    def test_live_list_shows_only_its_own_category(self):
        html = self.client.get(reverse('spare_subcategory_list', args=['spare_cable'])).content.decode()
        self.assertIn('ROUTE-CABLE-1', html)
        self.assertNotIn('ROUTE-BATTERY-1', html)
        self.assertNotIn('ROUTE-CABLE-SOLD', html)  # sold, not live

    def test_sold_list_scoped_to_category(self):
        html = self.client.get(reverse('inventory_sold', args=['spare_cable']), {'status': ''}).content.decode()
        self.assertIn('ROUTE-CABLE-SOLD', html)
        self.assertNotIn('ROUTE-BATTERY-1', html)

    def test_export_scoped_to_category(self):
        csv = self.client.get(reverse('inventory_export', args=['spare_cable', 'live'])).content.decode()
        self.assertIn('ROUTE-CABLE-1', csv)
        self.assertNotIn('ROUTE-BATTERY-1', csv)

    def test_unknown_kind_404s(self):
        self.assertEqual(self.client.get('/spare/spares/spare_not_a_real_one/').status_code, 404)


class DashboardCardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='dash', password='pass12345', email='d@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        from apps.categories.models import Spare

        cat = SpareCategory.objects.get_or_create(name='BATTERY')[0]
        for i, (status, store, out) in enumerate([
            ('LIVE', 'WH1', False), ('LIVE', 'WH1', False), ('FAULTY', 'WH2', False),
            ('SALE', 'WH1', True), ('SCRAP', 'WH1', True),
        ]):
            p = Product.objects.create(category=cat, serial_no=f'DASH-{i}', name=f'DASH-{i}')
            Spare.objects.create(product=p, barcode=f'DASH-BC-{i}')
            InventoryTransaction.objects.create(
                product=p, transaction_type='OUT' if out else 'IN',
                store_location=store, stock_status=status,
            )

    def test_kind_overview_matches_dashboard_and_endpoint(self):
        overview = card_data('spare_battery')
        self.assertEqual(overview['total'], 5)
        self.assertEqual(overview['in_stock'], 3)
        self.assertEqual(overview['sold'], 2)
        self.assertEqual(overview['faulty_damaged_in_stock'], 1)
        self.assertEqual(overview['faulty_damaged_scrap_out'], 1)
        self.assertEqual({s['store']: s['count'] for s in overview['by_store']}, {'WH1': 2, 'WH2': 1})

    def test_dashboard_page_and_detail_endpoint_agree(self):
        page = self.client.get(reverse('dashboard'))
        self.assertEqual(page.status_code, 200)
        detail = self.client.get(reverse('dashboard_card_detail', args=['spare_battery'])).json()
        self.assertEqual(detail['total'], 5)
        self.assertEqual(detail['list_url'], reverse('spare_subcategory_list', args=['spare_battery']))
        self.assertEqual(detail['sold_url'], reverse('inventory_sold', args=['spare_battery']))

    def test_unknown_card_404s(self):
        self.assertEqual(self.client.get(reverse('dashboard_card_detail', args=['nope'])).status_code, 404)

    def test_registry_covers_every_subcategory_and_server(self):
        registry = dashboard_registry()
        from apps.servers.groups import SERVER_GROUPS
        for slug in SERVER_GROUPS:
            self.assertIn(f'server_{slug}', registry)
        for slug in SPARE_SUBCATEGORIES:
            self.assertIn(spare_kind_key(slug), registry)


class SpareNavContextTests(TestCase):
    def test_nav_context_present_on_every_page(self):
        user = User.objects.create_superuser(username='navtest', password='pass12345', email='n@example.com')
        UserProfile.objects.create(user=user, role='ADMIN')
        self.client.force_login(user)
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('Add Cable', html)
        self.assertIn('Add Battery', html)


class MiscellaneousCatchAllTests(TestCase):
    """The exact product names from the real MISCELLANEOUS sheet, plus the
    IO Board group, pinned so a future change to the match sets can't
    silently misroute them."""

    MISC_NAMES = [
        'BATTERY BACKUP UNIT', 'BATTERY CARRIER', 'CARTRIDGE', 'FLASH DRIVE',
        'FRONT BEZEL', 'INTEL AC 8265 DUAL BAND 802.11', 'KEYBOARD',
        'LOGIC ACCESSORY CACHE', 'MOUSE', 'RAID KEY', 'TOE KEY',
    ]
    IO_BOARD_NAMES = ['IO BOARD', 'PASSTHRU CARD', 'PROCESSOR BOARD']

    def _spare_for(self, category_name):
        cat = SpareCategory.objects.get_or_create(name=category_name)[0]
        p = Product.objects.create(category=cat, serial_no=f'MISC-{category_name[:12]}', name=category_name)
        from apps.categories.models import Spare
        spare = Spare.objects.create(product=p, barcode=f'MISC-BC-{category_name[:12]}')
        InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')
        return spare

    def _subcategory_of(self, spare):
        hits = [slug for slug in SPARE_SUBCATEGORIES
                if type(spare).objects.filter(spare_subcategory_q(slug), pk=spare.pk).exists()]
        self.assertEqual(len(hits), 1, f'{spare.product.category.name} matched {hits}')
        return hits[0]

    def test_every_misc_sheet_name_lands_in_miscellaneous(self):
        for name in self.MISC_NAMES:
            spare = self._spare_for(name)
            self.assertEqual(self._subcategory_of(spare), 'miscellaneous', name)

    def test_io_board_group_lands_in_io_board(self):
        for name in self.IO_BOARD_NAMES:
            spare = self._spare_for(name)
            self.assertEqual(self._subcategory_of(spare), 'io_board', name)

    def test_miscellaneous_live_list_shows_these_items(self):
        user = User.objects.create_superuser(username='misctest', password='pass12345', email='m@example.com')
        UserProfile.objects.create(user=user, role='ADMIN')
        self.client.force_login(user)
        for name in self.MISC_NAMES:
            self._spare_for(name)
        html = self.client.get(reverse('spare_subcategory_list', args=['spare_miscellaneous'])).content.decode()
        for name in self.MISC_NAMES:
            self.assertIn(f'MISC-{name[:12]}', html)


class DedicatedLookalikeSpareTests(TestCase):
    """CARD/PROCESSOR/HARD DISK/MEMORY/SFP Spare rows (almost always a
    Controller's own child component, via Spare.controller) are excluded
    from every spare sub-category (including Miscellaneous) and shown
    read-only on the matching dedicated list page instead."""

    def setUp(self):
        from apps.categories.models import Controller, Spare
        self.user = User.objects.create_superuser(username='lookalike', password='pass12345', email='l@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)

        ctrl_cat = SpareCategory.objects.create(name='CONTROLLER')
        ctrl_product = Product.objects.create(category=ctrl_cat, serial_no='CTRL-LOOK-1', name='ctrl')
        self.controller = Controller.objects.create(product=ctrl_product, model='P440')

        card_cat = SpareCategory.objects.create(name='CARD')
        p = Product.objects.create(category=card_cat, serial_no='LOOK-CARD-1', name='LOOK-CARD-1')
        self.spare = Spare.objects.create(product=p, barcode='LOOK-CARD-BC-1', controller=self.controller)
        InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')

    def test_excluded_from_every_spare_subcategory(self):
        for slug in SPARE_SUBCATEGORIES:
            self.assertFalse(
                type(self.spare).objects.filter(spare_subcategory_q(slug), pk=self.spare.pk).exists(), slug)

    def test_shown_on_the_card_list_page_not_the_miscellaneous_page(self):
        card_html = self.client.get(reverse('card_list')).content.decode()
        self.assertIn('LOOK-CARD-1', card_html)
        self.assertIn('Also recorded as Spare parts under "Card"', card_html)
        self.assertIn('Controller: P440', card_html)

        misc_html = self.client.get(reverse('spare_subcategory_list', args=['spare_miscellaneous'])).content.decode()
        self.assertNotIn('LOOK-CARD-1', misc_html)

    def test_stocked_out_lookalike_spares_are_not_shown(self):
        InventoryTransaction.objects.create(
            product=self.spare.product, transaction_type='OUT', store_location='WH1', stock_status='SALE')
        card_html = self.client.get(reverse('card_list')).content.decode()
        self.assertNotIn('LOOK-CARD-1', card_html)


class SpareSubcategorySearchAndUniversalSearchTests(TestCase):
    """The live search box on a spare sub-category page must actually filter,
    and universal search must return each item once, labelled with its real
    category — not once per sub-category, all saying the sub-category name."""

    def setUp(self):
        from apps.categories.models import Spare
        self.user = User.objects.create_superuser(username='search', password='pass12345', email='se@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        misc_cat = SpareCategory.objects.get_or_create(name='FRONT BEZEL')[0]
        self.p1 = Product.objects.create(category=misc_cat, serial_no='SEARCHME-1', name='Front bezel A')
        self.s1 = Spare.objects.create(product=self.p1, barcode='MMISCA000456')
        InventoryTransaction.objects.create(product=self.p1, transaction_type='IN', store_location='WH1', stock_status='LIVE')

        self.p2 = Product.objects.create(category=misc_cat, serial_no='OTHERITEM-1', name='Front bezel B')
        Spare.objects.create(product=self.p2, barcode='UNRELATED-BC')
        InventoryTransaction.objects.create(product=self.p2, transaction_type='IN', store_location='WH1', stock_status='LIVE')

    def test_live_list_search_box_actually_filters(self):
        url = reverse('spare_subcategory_list', args=['spare_miscellaneous'])
        unfiltered = self.client.get(url).content.decode()
        self.assertIn('SEARCHME-1', unfiltered)
        self.assertIn('OTHERITEM-1', unfiltered)

        filtered = self.client.get(url, {'q': 'MMISCA000456'}).content.decode()
        self.assertIn('SEARCHME-1', filtered)
        self.assertNotIn('OTHERITEM-1', filtered)

    def test_universal_search_returns_one_result_not_nineteen(self):
        data = self.client.get(reverse('universal_search'), {'q': 'MMISCA000456'}).json()
        matches = [r for r in data['results'] if r['product_id'] == self.p1.id]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['type'], 'FRONT BEZEL')  # real category, not "Miscellaneous"

    def test_universal_search_type_reflects_real_category_for_every_subcategory(self):
        from apps.categories.models import Spare
        cable_cat = SpareCategory.objects.get_or_create(name='CABLE')[0]
        p = Product.objects.create(category=cable_cat, serial_no='CABLESEARCH-1', name='Cable X')
        Spare.objects.create(product=p, barcode='CABLESEARCH-BC')
        InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')

        data = self.client.get(reverse('universal_search'), {'q': 'CABLESEARCH'}).json()
        matches = [r for r in data['results'] if r['product_id'] == p.id]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['type'], 'CABLE')


class HardDiskSizeSplitTests(TestCase):
    """Hard Disk is split into 2.5" and 3.5" — same HardDisk model and
    fields, scoped by its own `size` field. No import changes needed: the
    existing single Hard Disk import already reads Size(2.5/3.5) per row."""

    def setUp(self):
        from apps.categories.models import HardDisk
        self.user = User.objects.create_superuser(username='hddsplit', password='pass12345', email='h@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        cat = SpareCategory.objects.get_or_create(name='HARD DISK')[0]

        def hdd(serial, size):
            p = Product.objects.create(category=cat, serial_no=serial, name=serial)
            HardDisk.objects.create(product=p, size=size, barcode=f'{serial}-BC')
            InventoryTransaction.objects.create(product=p, transaction_type='IN', store_location='WH1', stock_status='LIVE')
            return p
        self.p25 = hdd('HDD-25-1', '2.5')
        self.p35 = hdd('HDD-35-1', '3.5')

    def test_25_and_35_lists_are_mutually_exclusive(self):
        html25 = self.client.get(reverse('harddisk_25_list')).content.decode()
        self.assertIn('HDD-25-1', html25)
        self.assertNotIn('HDD-35-1', html25)

        html35 = self.client.get(reverse('harddisk_35_list')).content.decode()
        self.assertIn('HDD-35-1', html35)
        self.assertNotIn('HDD-25-1', html35)

    def test_combined_list_still_shows_both(self):
        html = self.client.get(reverse('harddisk_list')).content.decode()
        self.assertIn('HDD-25-1', html)
        self.assertIn('HDD-35-1', html)

    def test_sold_and_faulty_are_also_scoped_by_size(self):
        InventoryTransaction.objects.create(product=self.p25, transaction_type='OUT', store_location='WH1', stock_status='SALE')
        InventoryTransaction.objects.create(product=self.p35, transaction_type='OUT', store_location='WH1', stock_status='SALE')
        sold25 = self.client.get(reverse('inventory_sold', args=['harddisk_25']), {'status': ''}).content.decode()
        self.assertIn('HDD-25-1', sold25)
        self.assertNotIn('HDD-35-1', sold25)

    def test_dashboard_cards_split_by_size(self):
        page = self.client.get(reverse('dashboard'))
        self.assertEqual(page.status_code, 200)
        detail25 = self.client.get(reverse('dashboard_card_detail', args=['harddisk_25'])).json()
        detail35 = self.client.get(reverse('dashboard_card_detail', args=['harddisk_35'])).json()
        self.assertEqual(detail25['total'], 1)
        self.assertEqual(detail35['total'], 1)
        self.assertEqual(detail25['list_url'], reverse('harddisk_25_list'))


@override_settings(EMAIL_BACKEND=LOCMEM)
class HardDiskSizeImportTests(TestCase):
    """The Hard Disk 2.5"/3.5" imports force size like the spare
    sub-category imports force category — the sheet has no Size(2.5/3.5)
    column, so the import option decides it."""

    def setUp(self):
        override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        override.enable()
        self.addCleanup(override.disable)

    def test_stock_in_forces_the_chosen_size_no_size_column_needed(self):
        from apps.categories.models import HardDisk
        headers = list(HEADER_MAPS['harddisk_25'])
        self.assertNotIn('Size(2.5/3.5)', headers)
        job = _run_import('harddisk_25', _xlsx_upload(headers, [
            _row(headers, Brand='SEAGATE', **{'Serial No': 'HDD25-SN-1', 'Barcode': 'HDD25-BC-1'}),
        ]))
        self.assertEqual((job.success_count, job.error_count), (1, 0), job.errors)
        self.assertEqual(HardDisk.objects.get(barcode='HDD25-BC-1').size, '2.5')

        job2 = _run_import('harddisk_35', _xlsx_upload(headers, [
            _row(headers, Brand='SEAGATE', **{'Serial No': 'HDD35-SN-1', 'Barcode': 'HDD35-BC-1'}),
        ]))
        self.assertEqual((job2.success_count, job2.error_count), (1, 0), job2.errors)
        self.assertEqual(HardDisk.objects.get(barcode='HDD35-BC-1').size, '3.5')

    def test_import_page_lists_both_sizes_and_their_stock_out_variant(self):
        for key, label in [('harddisk_25', '2.5" Hard Disk'), ('harddisk_35', '3.5" Hard Disk')]:
            self.assertEqual(IMPORT_LABELS[key], label)
            self.assertIn(f'{key}_stock_out', IMPORT_LABELS)


@override_settings(EMAIL_BACKEND=LOCMEM)
class ServerGroupImportTests(TestCase):
    def setUp(self):
        override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        override.enable()
        self.addCleanup(override.disable)

    def _rows(self, headers, tag, machine_type, model, spares):
        return [_row(headers, **{'Machine Type': machine_type, 'System Service Tag No': tag, 'Model': model,
                                 'Spares Type': st, 'Serial No': f'{tag}-{i}', 'QTY': 1})
                for i, st in enumerate(spares)]

    def test_group_import_forces_group_even_when_machine_type_is_ambiguous(self):
        from apps.servers.models import Server
        headers = list(HEADER_MAPS['server_sun_servers'])
        job = _run_import('server_sun_servers', _xlsx_upload(headers, self._rows(
            headers, 'SUNTAG1', 'RACK SERVER', 'Generic Model', ['CABINET', 'MOTHER BOARD'])))
        self.assertEqual(job.error_count, 0, job.errors)
        self.assertEqual(Server.objects.get(service_tag='SUNTAG1').group, 'sun_servers')

    def test_generic_server_import_infers_group(self):
        from apps.servers.models import Server
        headers = list(HEADER_MAPS['server'])
        job = _run_import('server', _xlsx_upload(headers, self._rows(
            headers, 'CSC1', 'CHASSIS', 'CISCO UCS 5108', ['CABINET']) + self._rows(
            headers, 'SW1', 'SWITCH', 'CISCO 2960', ['CABINET'])))
        self.assertEqual(job.error_count, 0, job.errors)
        self.assertEqual(Server.objects.get(service_tag='CSC1').group, 'cisco_chassis')
        self.assertEqual(Server.objects.get(service_tag='SW1').group, 'networking_switch')

    def test_import_page_lists_every_group(self):
        from apps.servers.groups import SERVER_GROUPS
        for slug, cfg in SERVER_GROUPS.items():
            self.assertEqual(IMPORT_LABELS[f'server_{slug}'], cfg['label'])
            self.assertIn(f'server_{slug}_stock_out', IMPORT_LABELS)


@override_settings(EMAIL_BACKEND=LOCMEM)
class MissingServiceTagImportTests(TestCase):
    """A server row with no System Service Tag No is still stored: its rows
    are grouped by Machine no and the machine is flagged as tag-missing."""

    def setUp(self):
        override = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_superuser(username='notag', password='pass12345', email='n@example.com')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)

    def _row(self, headers, machine_no, spare, serial, tag=''):
        return _row(headers, **{'Machine Type': 'CHASSIS', 'Machine no': machine_no, 'System Service Tag No': tag,
                                'Model': 'CISCO UCS 5108', 'Spares Type': spare, 'Serial No': serial, 'QTY': 1})

    def test_rows_without_tag_are_stored_and_grouped_by_machine_no(self):
        from apps.servers.models import Server
        headers = list(HEADER_MAPS['server_cisco_chassis'])
        job = _run_import('server_cisco_chassis', _xlsx_upload(headers, [
            self._row(headers, 'MUM CIS CHA 031', 'CABINET', 'NT-1'),
            self._row(headers, 'MUM CIS CHA 031', 'POWER SUPPLY', 'NT-2'),
            self._row(headers, 'MUM CIS CHA 032', 'CABINET', 'NT-3'),
            self._row(headers, '', 'CABINET', 'NT-4'),  # no tag and no machine no -> still an error
        ]))
        self.assertEqual((job.success_count, job.error_count), (3, 1), job.errors)
        self.assertIn('Machine no', job.errors[0]['error'])
        servers = Server.objects.filter(service_tag_missing=True).order_by('machine_no')
        self.assertEqual([s.machine_no for s in servers], ['MUM CIS CHA 031', 'MUM CIS CHA 032'])
        self.assertEqual(servers[0].components.count(), 2)

        html = self.client.get(reverse('server_group_list', args=['cisco_chassis'])).content.decode()
        self.assertIn('title="System Service Tag No is missing"', html)
        self.assertNotIn('NOTAG-MUM CIS CHA 031</code>', html)


class UniversalSearchInStockOnlyTests(TestCase):
    """Universal search lists only in-stock items, flags faulty / damaged ones,
    and a stocked-out item can never be stocked out a second time."""

    def setUp(self):
        from apps.categories.models import Spare
        self.user = User.objects.create_user(username='us-admin', password='pass12345')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        cat = SpareCategory.objects.get_or_create(name='FRONT BEZEL')[0]
        self.items = {}
        for code, status in (('LIVEONE', 'LIVE'), ('FAULTYONE', 'FAULTY'), ('DAMAGEDONE', 'DAMAGED')):
            product = Product.objects.create(category=cat, serial_no=f'USRCH-{code}', name=code)
            Spare.objects.create(product=product, barcode=f'USRCH-BC-{code}')
            InventoryTransaction.objects.create(product=product, transaction_type='IN', store_location='WH1', stock_status=status)
            self.items[code] = product

    def _results(self):
        data = self.client.get(reverse('universal_search'), {'q': 'USRCH'}).json()
        return {r['product_id']: r for r in data['results']}

    def test_stocked_out_item_disappears_and_faulty_damaged_carry_status(self):
        results = self._results()
        self.assertEqual(results[self.items['LIVEONE'].id]['status'], 'LIVE')
        self.assertEqual(results[self.items['FAULTYONE'].id]['status'], 'FAULTY')
        self.assertEqual(results[self.items['DAMAGEDONE'].id]['status'], 'DAMAGED')

        res = self.client.post(reverse('stock_out'), {'product_id': self.items['LIVEONE'].id, 'stock_status': 'SALE'})
        self.assertTrue(res.json()['success'])
        self.assertNotIn(self.items['LIVEONE'].id, self._results())

    def test_second_stock_out_is_rejected(self):
        url = reverse('stock_out')
        pid = self.items['LIVEONE'].id
        self.assertTrue(self.client.post(url, {'product_id': pid, 'stock_status': 'SALE'}).json()['success'])
        again = self.client.post(url, {'product_id': pid, 'stock_status': 'SALE'}).json()
        self.assertFalse(again['success'])
        self.assertIn('already stocked out', again['error'])
        self.assertEqual(InventoryTransaction.objects.filter(product_id=pid, transaction_type='OUT').count(), 1)

    def test_stocked_out_server_is_hidden(self):
        server_cat = SpareCategory.objects.get_or_create(name='SERVER')[0]
        server_product = Product.objects.create(category=server_cat, serial_no='USRCH-SRV', name='Server')
        Server.objects.create(product=server_product, service_tag='USRCH-SRV', machine_no='M1', group='rack_server')
        InventoryTransaction.objects.create(product=server_product, transaction_type='IN', store_location='WH1', stock_status='LIVE')
        self.assertIn(server_product.id, self._results())
        InventoryTransaction.objects.create(product=server_product, transaction_type='OUT', store_location='WH1', stock_status='SALE')
        self.assertNotIn(server_product.id, self._results())


class ReadOnlyRoleTests(TestCase):
    def _login(self, role):
        user = User.objects.create_user(username=f'ro-{role.lower()}', password='pass12345')
        UserProfile.objects.create(user=user, role=role)
        self.client.force_login(user)
        return user

    def test_anonymous_must_log_in_for_live_lists_and_search(self):
        for name, args in (('spare_list', []), ('card_list', []), ('server_list', []),
                           ('server_group_list', ['rack_server']), ('server_empty_list', []),
                           ('spare_subcategory_list', ['spare_cable']), ('controller_list', [])):
            res = self.client.get(reverse(name, args=args))
            self.assertEqual(res.status_code, 302, name)
            self.assertIn(reverse('home'), res['Location'])
        self.assertEqual(self.client.get(reverse('universal_search'), {'q': 'abc'}).status_code, 302)
        self.assertNotIn('View without login', self.client.get(reverse('home')).content.decode())

    def test_readonly_live_sees_live_lists_only_and_cannot_act(self):
        self._login('READONLY_LIVE')
        self.assertEqual(self.client.get(reverse('card_list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('server_group_list', args=['rack_server'])).status_code, 200)
        self.assertEqual(self.client.get(reverse('universal_search'), {'q': 'abc'}).status_code, 200)
        self.assertEqual(self.client.get(reverse('inventory_sold', args=['card'])).status_code, 403)
        self.assertEqual(self.client.get(reverse('server_out_list')).status_code, 403)
        self.assertEqual(self.client.post(reverse('stock_out'), {'product_id': 1}).status_code, 403)
        self.assertEqual(self.client.get(reverse('inventory_import')).status_code, 403)
        page = self.client.get(reverse('card_list')).content.decode()
        for flag in ('canStockOut', 'canMap', 'canAudit', 'canFreeze', 'canStatusUpdate'):
            self.assertIn(f'const {flag} = false;', page)
        self.assertIn('id="universalSearchInput"', page)
        self.assertNotIn(reverse('inventory_sold', args=['card']), page)

    def test_readonly_out_sees_out_lists_only_and_cannot_act(self):
        self._login('READONLY_OUT')
        self.assertEqual(self.client.get(reverse('card_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('server_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('universal_search'), {'q': 'abc'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('inventory_sold', args=['card'])).status_code, 200)
        self.assertEqual(self.client.get(reverse('inventory_faulty', args=['card'])).status_code, 200)
        self.assertEqual(self.client.get(reverse('server_group_out_list', args=['rack_server'])).status_code, 200)
        self.assertEqual(self.client.get(reverse('stock_out_status_list', args=['RENT'])).status_code, 200)
        self.assertEqual(self.client.post(reverse('stock_out'), {'product_id': 1}).status_code, 403)
        page = self.client.get(reverse('dashboard')).content.decode()
        self.assertNotIn('href="' + reverse('card_list') + '"', page)
        self.assertNotIn('id="universalSearchInput"', page)
        self.assertIn(reverse('inventory_sold', args=['card']), page)

    def test_existing_roles_keep_live_access_by_default(self):
        for role in ('ADMIN', 'STOCK_IN', 'STOCK_OUT', 'AUDIT'):
            user = User.objects.create_user(username=f'def-{role}', password='x')
            UserProfile.objects.create(user=user, role=role)
            self.assertTrue(has_permission(user, 'view_live'), role)


class RoleResetTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='reset-admin', password='pass12345')
        UserProfile.objects.create(user=self.admin, role='ADMIN')
        self.client.force_login(self.admin)

    def test_reset_to_default_removes_customisation(self):
        RolePermission.objects.create(role='STOCK_IN', permissions=['user_management'])
        res = self.client.post(reverse('role_permission_settings'), {'role': 'STOCK_IN', 'action': 'reset'})
        self.assertRedirects(res, reverse('role_permission_settings'))
        self.assertFalse(RolePermission.objects.filter(role='STOCK_IN').exists())
        user = User.objects.create_user(username='reset-stock-in', password='x')
        UserProfile.objects.create(user=user, role='STOCK_IN')
        self.assertTrue(has_permission(user, 'stock_in'))
        self.assertFalse(has_permission(user, 'user_management'))

    def test_settings_page_lists_new_roles_and_reset_button(self):
        RolePermission.objects.create(role='AUDIT', permissions=['audit'])
        html = self.client.get(reverse('role_permission_settings')).content.decode()
        self.assertIn('Read-only: Live Stock', html)
        self.assertIn('Read-only: Out Stock', html)
        self.assertIn('Reset to Default', html)
        self.assertIn('Read-only: view live (in-stock) lists', html)

    def test_reset_of_admin_restores_full_access(self):
        RolePermission.objects.create(role='ADMIN', permissions=['user_management'])
        self.assertEqual(self.client.get(reverse('card_list')).status_code, 403)
        self.client.post(reverse('role_permission_settings'), {'role': 'ADMIN', 'action': 'reset'})
        self.assertEqual(self.client.get(reverse('card_list')).status_code, 200)


def _barcoded_item(code, status='LIVE', category='FRONT BEZEL'):
    from apps.categories.models import Spare
    cat = SpareCategory.objects.get_or_create(name=category)[0]
    product = Product.objects.create(category=cat, serial_no=f'SN-{code}', name=code)
    Spare.objects.create(product=product, barcode=code)
    InventoryTransaction.objects.create(product=product, transaction_type='IN', store_location='WH1', stock_status=status)
    return product


class TodayOnlyDateTests(TestCase):
    """Entry dates are always today; only a rental's expected return date may
    be in the future (never in the past)."""

    def setUp(self):
        self.user = User.objects.create_user(username='date-admin', password='pass12345')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)
        from django.utils import timezone
        self.today = timezone.localdate()

    def test_back_or_future_stock_out_date_is_ignored(self):
        for code, sent in (('DT-BACK', '2020-01-01'), ('DT-FUT', '2099-01-01')):
            product = _barcoded_item(code)
            res = self.client.post(reverse('stock_out'), {'product_id': product.id, 'stock_status': 'SALE', 'stock_out_date': sent})
            self.assertTrue(res.json()['success'])
            out = product.transactions.get(transaction_type='OUT')
            self.assertEqual(out.stock_out_date, self.today)

    def test_rental_expected_return_future_ok_past_rejected(self):
        from datetime import timedelta
        from apps.inventory.models import RentalRecord
        past = _barcoded_item('DT-RENT-PAST')
        res = self.client.post(reverse('stock_out'), {
            'product_id': past.id, 'stock_status': 'RENT',
            'expected_return_date': (self.today - timedelta(days=1)).isoformat()})
        self.assertFalse(res.json()['success'])
        self.assertIn('past', res.json()['error'])
        self.assertFalse(past.transactions.filter(transaction_type='OUT').exists())

        future = _barcoded_item('DT-RENT-FUT')
        when = self.today + timedelta(days=30)
        res = self.client.post(reverse('stock_out'), {
            'product_id': future.id, 'stock_status': 'RENT', 'expected_return_date': when.isoformat()})
        self.assertTrue(res.json()['success'])
        self.assertEqual(RentalRecord.objects.get(product=future).expected_return_date, when)

    def test_audit_and_sales_return_use_today(self):
        product = _barcoded_item('DT-AUDIT')
        self.client.post(reverse('audit_spare'), {'product_id': product.id, 'audited_on': '2020-05-05', 'audit_result': 'FOUND'})
        self.assertEqual(product.transactions.get(transaction_type='AUDIT').audited_on, self.today)

        self.client.post(reverse('stock_out'), {'product_id': product.id, 'stock_status': 'SALE'})
        res = self.client.post(reverse('sales_return'), {'product_id': product.id, 'reason': 'NORMAL', 'returned_on': '2020-05-05'})
        self.assertTrue(res.json()['success'])
        from apps.inventory.models import SalesReturn
        self.assertEqual(SalesReturn.objects.get(product=product).returned_on, self.today)

    def test_date_inputs_are_marked_today_only(self):
        html = self.client.get(reverse('card_list')).content.decode()
        self.assertIn('id="stockOutDate" class="today-only', html)
        self.assertIn('id="stockOutReturnDate" class="future-only', html)
        self.assertIn('function todayLocal()', html)


class CustomUserTypeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='type-admin', password='pass12345')
        UserProfile.objects.create(user=self.admin, role='ADMIN')
        self.client.force_login(self.admin)
        self.url = reverse('role_permission_settings')

    def _add(self, label, copy_from=''):
        return self.client.post(self.url, {'action': 'add_role', 'label': label, 'copy_from': copy_from})

    def test_add_user_type_assign_user_and_permissions_apply(self):
        self._add('Store Manager', copy_from='READONLY_LIVE')
        row = RolePermission.objects.get(label='Store Manager')
        self.assertTrue(row.is_custom)
        self.assertEqual(row.role, 'STORE_MANAGER')
        self.assertEqual(row.permissions, ['view_live'])

        self.assertIn('Store Manager', self.client.get(reverse('user_create')).content.decode())
        res = self.client.post(reverse('user_create'), {'username': 'mgr', 'password': 'x12345678', 'role': 'STORE_MANAGER'})
        self.assertRedirects(res, reverse('user_list'))
        mgr = User.objects.get(username='mgr')
        self.assertEqual(mgr.profile.role, 'STORE_MANAGER')
        self.assertEqual(mgr.profile.get_role_display(), 'Store Manager')
        self.assertTrue(has_permission(mgr, 'view_live'))
        self.assertFalse(has_permission(mgr, 'stock_out'))
        self.assertIn('Store Manager', self.client.get(reverse('user_list')).content.decode())

        self.client.post(self.url, {'role': 'STORE_MANAGER', 'view_live': 'on', 'stock_out': 'on'})
        self.assertTrue(has_permission(mgr, 'stock_out'))

    def test_duplicate_or_blank_name_rejected(self):
        self._add('Store Manager')
        self._add('store manager')
        self._add('Admin')
        self._add('   ')
        self.assertEqual(RolePermission.objects.filter(is_custom=True).count(), 1)

    def test_delete_only_when_unused_and_reset_not_allowed(self):
        self._add('Temp Type')
        user = User.objects.create_user(username='temp-user', password='x')
        UserProfile.objects.create(user=user, role='TEMP_TYPE')
        self.client.post(self.url, {'role': 'TEMP_TYPE', 'action': 'reset'})
        self.assertTrue(RolePermission.objects.filter(role='TEMP_TYPE').exists())
        self.client.post(self.url, {'role': 'TEMP_TYPE', 'action': 'delete_role'})
        self.assertTrue(RolePermission.objects.filter(role='TEMP_TYPE').exists())
        user.profile.role = 'STOCK_IN'
        user.profile.save()
        self.client.post(self.url, {'role': 'TEMP_TYPE', 'action': 'delete_role'})
        self.assertFalse(RolePermission.objects.filter(role='TEMP_TYPE').exists())

    def test_builtin_role_cannot_be_deleted(self):
        RolePermission.objects.create(role='AUDIT', permissions=['audit'])
        self.client.post(self.url, {'role': 'AUDIT', 'action': 'delete_role'})
        self.assertTrue(RolePermission.objects.filter(role='AUDIT').exists())


class BulkExcelUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bulk-admin', password='pass12345')
        UserProfile.objects.create(user=self.user, role='ADMIN')
        self.client.force_login(self.user)

    def _xlsx(self, rows):
        book = Workbook()
        for row in rows:
            book.active.append(row)
        stream = BytesIO()
        book.save(stream)
        return SimpleUploadedFile('bulk.xlsx', stream.getvalue())

    def _read(self, kind, rows):
        return self.client.post(reverse('bulk_update_read', args=[kind]), {'file': self._xlsx(rows)}).json()

    def _apply(self, kind, rows, reason=''):
        import json
        return self.client.post(reverse('bulk_update_apply', args=[kind]), json.dumps({'rows': rows, 'reason': reason}),
                                content_type='application/json').json()

    def test_page_and_templates(self):
        self.assertEqual(self.client.get(reverse('bulk_update')).status_code, 200)
        for kind, headers in (('freeze', ['Barcode No', 'Remark']), ('status', ['Barcode No', 'Status', 'Remark'])):
            res = self.client.get(reverse('bulk_update_template', args=[kind]))
            sheet = load_workbook(BytesIO(res.content)).active
            self.assertEqual([c.value for c in sheet[1]], headers)

    def test_bulk_freeze_across_categories(self):
        a = _barcoded_item('BF-1', category='FRONT BEZEL')
        b = _barcoded_item('BF-2', category='CABLE')
        sold = _barcoded_item('BF-3')
        InventoryTransaction.objects.create(product=sold, transaction_type='OUT', store_location='WH1', stock_status='SALE')
        data = self._read('freeze', [['Barcode No', 'Remark'], ['bf-1', 'Customer hold'], ['BF-2', None],
                                     ['BF-3', None], ['NOPE-9', None], ['BF-1', 'again']])
        self.assertTrue(data['success'])
        self.assertEqual([r['barcode'] for r in data['rows']], ['bf-1', 'BF-2', 'BF-3', 'NOPE-9'])
        self.assertIn('repeated', data['errors'][0]['message'])

        results = {r['barcode']: r for r in self._apply('freeze', data['rows'], reason='Audit hold')['results']}
        self.assertTrue(results['bf-1']['ok'])
        self.assertTrue(results['BF-2']['ok'])
        self.assertIn('Stocked out', results['BF-3']['message'])
        self.assertEqual(results['NOPE-9']['message'], 'Barcode not found')
        self.assertEqual(a.freeze_records.get().reason, 'Customer hold')
        self.assertEqual(b.freeze_records.get().reason, 'Audit hold')
        again = self._apply('freeze', [{'row': 2, 'barcode': 'BF-1'}], reason='x')['results'][0]
        self.assertEqual(again['message'], 'Already frozen')

    def test_bulk_freeze_needs_a_reason(self):
        _barcoded_item('BF-NR')
        result = self._apply('freeze', [{'row': 2, 'barcode': 'BF-NR', 'remark': ''}])['results'][0]
        self.assertFalse(result['ok'])
        self.assertIn('Remark is required', result['message'])

    def test_bulk_status_update(self):
        a = _barcoded_item('BS-1')
        b = _barcoded_item('BS-2')
        data = self._read('status', [['Barcode No', 'Status', 'Remark'], ['BS-1', 'Faulty', 'No POST'],
                                     ['BS-2', 'adv replacement', 'x'], ['BS-2', 'DAMAGED', ''],
                                     ['BS-3', 'Damaged', '']])
        self.assertEqual([r['barcode'] for r in data['rows']], ['BS-1'])
        messages = {e['row']: e['message'] for e in data['errors']}
        self.assertIn('not a status', messages[3])
        self.assertIn('repeated', messages[4])
        self.assertIn('Remark is required', messages[5])

        rows = data['rows'] + [{'row': 9, 'barcode': 'BS-2', 'status': 'DAMAGED', 'remark': 'Cracked'}]
        results = self._apply('status', rows)['results']
        self.assertTrue(all(r['ok'] for r in results))
        self.assertEqual(a.transactions.order_by('-id').first().stock_status, 'FAULTY')
        self.assertEqual(b.transactions.order_by('-id').first().stock_status, 'DAMAGED')

    def test_missing_column_is_reported(self):
        data = self._read('status', [['Barcode No', 'Remark'], ['X', 'y']])
        self.assertFalse(data['success'])
        self.assertIn('Status', data['error'])

    def test_permission_required(self):
        viewer = User.objects.create_user(username='bulk-viewer', password='x')
        UserProfile.objects.create(user=viewer, role='READONLY_LIVE')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('bulk_update')).status_code, 403)
        self.assertEqual(self.client.post(reverse('bulk_update_read', args=['freeze'])).status_code, 403)
        self.assertEqual(self.client.post(reverse('bulk_update_apply', args=['status']), '{}', content_type='application/json').status_code, 403)


class RolePermissionExportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='export-admin', password='pass12345', email='a@example.com')
        UserProfile.objects.create(user=self.admin, role='ADMIN')
        viewer = User.objects.create_user(username='export-viewer', password='x')
        UserProfile.objects.create(user=viewer, role='READONLY_OUT')
        RolePermission.objects.create(role='STORE_MANAGER', label='Store Manager', is_custom=True, permissions=['view_live'])
        mgr = User.objects.create_user(username='export-mgr', password='x')
        UserProfile.objects.create(user=mgr, role='STORE_MANAGER')

    def test_export_lists_every_type_permission_and_user(self):
        self.client.force_login(self.admin)
        res = self.client.get(reverse('role_permission_export'))
        self.assertEqual(res.status_code, 200)
        book = load_workbook(BytesIO(res.content))
        self.assertEqual(book.sheetnames[:3], ['Role Permissions', 'User Types', 'Users'])

        matrix = book['Role Permissions']
        header = [c.value for c in matrix[4]]
        for label in ('Admin', 'Stock In User', 'Read-only: Live Stock', 'Read-only: Out Stock', 'Store Manager'):
            self.assertIn(label, header)
        rows = {r[0]: r for r in matrix.iter_rows(min_row=5, values_only=True) if r[0]}
        live_row = rows['Read-only: view live (in-stock) lists and search']
        self.assertEqual(live_row[header.index('Store Manager')], 'Yes')
        self.assertIsNone(live_row[header.index('Read-only: Out Stock')])
        self.assertEqual(rows['Manage users and role settings'][header.index('Admin')], 'Yes')

        types = {r[0]: r for r in book['User Types'].iter_rows(min_row=5, values_only=True) if r[0]}
        self.assertEqual(types['Store Manager'][1], 'Added type')
        self.assertEqual(types['Store Manager'][3], 'export-mgr')

        users = {r[0]: r for r in book['Users'].iter_rows(min_row=5, values_only=True) if r[0]}
        self.assertEqual(users['export-viewer'][3], 'Read-only: Out Stock')
        self.assertEqual(users['export-mgr'][3], 'Store Manager')

    def test_export_needs_user_management(self):
        viewer = User.objects.get(username='export-viewer')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('role_permission_export')).status_code, 403)
