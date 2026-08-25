import fs from 'node:fs/promises';
import { SpreadsheetFile, Workbook } from '@oai/artifact-tool';

const outputDir = 'outputs/role-operations-guide';
const wb = Workbook.create();
const summary = wb.worksheets.add('Guide');
const matrix = wb.worksheets.add('Role Matrix');
const processes = wb.worksheets.add('Processes');

const navy = '#12355B';
const blue = '#1D6FB8';
const pale = '#EAF2F8';
const green = '#E8F5E9';
const border = '#C9D6E3';
const headerFormat = { fill: navy, font: { bold: true, color: '#FFFFFF' }, horizontalAlignment: 'center', verticalAlignment: 'center', wrapText: true };

summary.showGridLines = false;
summary.mergeCells('A1:F1');
summary.getRange('A1').values = [['Inventory Management - Operations and Access Guide']];
summary.getRange('A1:F1').format = { fill: navy, font: { bold: true, color: '#FFFFFF', size: 16 }, horizontalAlignment: 'left', verticalAlignment: 'center' };
summary.getRange('A1:F1').format.rowHeight = 30;
summary.getRange('A3:F3').values = [['Purpose', 'This workbook documents the implemented inventory workflows, default role access, and the role settings screen used to customize access.', '', '', '', '']];
summary.mergeCells('B3:F3');
summary.getRange('A3:F3').format = { fill: pale, wrapText: true, verticalAlignment: 'top', borders: { preset: 'outside', style: 'thin', color: border } };
summary.getRange('A3').format.font = { bold: true, color: navy };
summary.getRange('A5:C5').values = [['Where to manage access', 'What it controls', 'Notes']];
summary.getRange('A5:C5').format = headerFormat;
summary.getRange('A6:C8').values = [
  ['Administration > User Management', 'Create users, set each user role, disable users, reset passwords.', 'Only users with Manage users and role settings can access it.'],
  ['Administration > Role Settings', 'Choose which functions every role can use.', 'Changes apply immediately. Admin always retains role-settings access.'],
  ['Role Matrix sheet', 'The default access delivered with the system.', 'A role marked Custom in the app has an administrator-saved override.'],
];
summary.getRange('A5:C8').format.borders = { preset: 'all', style: 'thin', color: border };
summary.getRange('A5:C8').format.wrapText = true;
summary.getRange('A10:F10').values = [['Operational safeguards', 'Implemented behavior', '', '', '', '']];
summary.mergeCells('B10:F10');
summary.getRange('A10:F10').format = { fill: green, wrapText: true, borders: { preset: 'outside', style: 'thin', color: border } };
summary.getRange('A10').format.font = { bold: true, color: navy };
summary.getRange('A11:F15').values = [
  ['Stock-out records', 'Every status is retained, including SALE, RENT, TESTING, REPLACEMENT, ADV_REPLACEMENT, ON_APPROVAL, EMPTY, REFILL, SCRAP, FAULTY and DAMAGED.', '', '', '', ''],
  ['Returns', 'Stock In users process sale and status returns; return reason, warehouse, location, and dated remarks are recorded.', '', '', '', ''],
  ['Transfers', 'Requests require different source and destination stores. A Stock In user or Admin receives stock one-by-one or by Excel and supplies the destination location.', '', '', '', ''],
  ['Inline remarks', 'Remarks append a dated entry to the underlying asset; only users with Mapping permission may update them.', '', '', '', ''],
  ['Audit trail', 'Stock, return, audit, transfer, mapping, and other activities are retained in the product ledger and activity trail.', '', '', '', ''],
];
for (let r = 11; r <= 15; r++) summary.mergeCells(`B${r}:F${r}`);
summary.getRange('A11:F15').format = { borders: { preset: 'all', style: 'thin', color: border }, wrapText: true, verticalAlignment: 'top' };
summary.getRange('A11:A15').format.font = { bold: true, color: navy };
summary.getRange('A:A').format.columnWidth = 28;
summary.getRange('B:B').format.columnWidth = 36;
summary.getRange('C:C').format.columnWidth = 36;
summary.getRange('D:F').format.columnWidth = 15;
summary.getRange('3:15').format.rowHeight = 34;

const permissions = [
  ['Manage users and role settings', 'Create users, change roles, and configure role permissions'],
  ['Add stock and components', 'Add inventory records, stock-in products, add server/controller components'],
  ['Stock out products', 'Stock out a single product and select its status'],
  ['Import stock-out Excel files', 'Process stock-out Excel uploads'],
  ['Create transfer requests', 'Create individual or Excel-based stock transfer requests'],
  ['Receive and approve transfers', 'Approve individual transfers or bulk-receive using Excel'],
  ['Perform single-product audits', 'Submit a physical audit for a product'],
  ['View audit reports and findings', 'Open audit reports, findings, and general findings'],
  ['Create audit and general findings', 'Submit audit findings and general audit findings'],
  ['Attend audit findings', 'Mark a finding attended and add an attendance remark'],
  ['View product history and ledgers', 'Open movement ledger, audit history, and product timeline'],
  ['Process sales returns', 'Return sold stock to live or faulty stock with warehouse/location'],
  ['Return non-sale stocked-out products', 'Return RENT, TESTING, REPLACEMENT and other status stock'],
  ['Process rental returns', 'Process a rental return'],
  ['View sold, faulty, and stock-status lists', 'Open sold, faulty, rental, and status list views'],
  ['Reconcile audit differences', 'Run audit reconciliation actions'],
  ['Map products and update list remarks', 'Map components and append inline product remarks'],
  ['Freeze and unfreeze stock', 'Freeze or unfreeze eligible stock'],
  ['View and export reports', 'Open reports and download exports'],
];
matrix.showGridLines = false;
matrix.mergeCells('A1:F1');
matrix.getRange('A1').values = [['Default Role Access Matrix']];
matrix.getRange('A1:F1').format = { fill: navy, font: { bold: true, color: '#FFFFFF', size: 15 }, verticalAlignment: 'center' };
matrix.getRange('A1:F1').format.rowHeight = 28;
matrix.getRange('A3:F3').values = [['Function / permission', 'What it allows', 'Admin', 'Stock In', 'Stock Out', 'Audit']];
matrix.getRange('A3:F3').format = headerFormat;
const allowed = {
  'Manage users and role settings': ['Admin'],
  'Add stock and components': ['Admin', 'Stock In'],
  'Stock out products': ['Admin', 'Stock Out'],
  'Import stock-out Excel files': ['Admin', 'Stock Out'],
  'Create transfer requests': ['Admin', 'Stock Out'],
  'Receive and approve transfers': ['Admin', 'Stock In'],
  'Perform single-product audits': ['Admin', 'Audit'],
  'View audit reports and findings': ['Admin', 'Stock In'],
  'Create audit and general findings': ['Admin', 'Stock In', 'Audit'],
  'Attend audit findings': ['Admin', 'Stock In'],
  'View product history and ledgers': ['Admin', 'Stock In'],
  'Process sales returns': ['Admin', 'Stock In'],
  'Return non-sale stocked-out products': ['Admin', 'Stock In'],
  'Process rental returns': ['Admin', 'Stock In'],
  'View sold, faulty, and stock-status lists': ['Admin', 'Stock In', 'Stock Out'],
  'Reconcile audit differences': ['Admin'],
  'Map products and update list remarks': ['Admin', 'Stock In', 'Stock Out'],
  'Freeze and unfreeze stock': ['Admin', 'Stock Out'],
  'View and export reports': ['Admin', 'Stock In', 'Stock Out'],
};
const roleNames = ['Admin', 'Stock In', 'Stock Out', 'Audit'];
const matrixRows = permissions.map(([permission, detail]) => [permission, detail, ...roleNames.map(role => allowed[permission].includes(role) ? 'Allowed' : 'Not allowed')]);
matrix.getRange(`A4:F${3 + matrixRows.length}`).values = matrixRows;
matrix.getRange(`A3:F${3 + matrixRows.length}`).format.borders = { preset: 'all', style: 'thin', color: border };
matrix.getRange(`A4:B${3 + matrixRows.length}`).format.wrapText = true;
matrix.getRange(`C4:F${3 + matrixRows.length}`).format.horizontalAlignment = 'center';
matrixRows.forEach((row, rowIndex) => {
  row.slice(2).forEach((value, columnOffset) => {
    matrix.getCell(rowIndex + 3, columnOffset + 2).format = value === 'Allowed'
      ? { fill: '#DDF2E1', font: { color: '#146C2E', bold: true }, horizontalAlignment: 'center' }
      : { fill: '#F7E3E5', font: { color: '#9D2430' }, horizontalAlignment: 'center' };
  });
});
matrix.freezePanes.freezeRows(3);
matrix.getRange('A:A').format.columnWidth = 36;
matrix.getRange('B:B').format.columnWidth = 52;
matrix.getRange('C:F').format.columnWidth = 16;
matrix.getRange(`4:${3 + matrixRows.length}`).format.rowHeight = 30;

processes.showGridLines = false;
processes.mergeCells('A1:D1');
processes.getRange('A1').values = [['Inventory Process Reference']];
processes.getRange('A1:D1').format = { fill: navy, font: { bold: true, color: '#FFFFFF', size: 15 }, verticalAlignment: 'center' };
processes.getRange('A1:D1').format.rowHeight = 28;
processes.getRange('A3:D3').values = [['Process', 'Who performs it by default', 'Steps', 'Record retained']];
processes.getRange('A3:D3').format = headerFormat;
processes.getRange('A4:D13').values = [
  ['Stock in / Excel import', 'Admin, Stock In', 'Add individually or import the model-specific Excel. The importer creates product and stock-in records.', 'Inventory transaction, product, activity log, timeline'],
  ['Stock out', 'Admin, Stock Out', 'Choose product, client/invoice/OLF details, status, and date. Server/controller components follow parent stock out.', 'Stock-out transaction, activity log, timeline'],
  ['Sales return', 'Admin, Stock In', 'Choose a sold item, return reason, destination (live/faulty), warehouse, location, and remarks.', 'Sales return record, stock transaction, dated asset remark, timeline'],
  ['Status return', 'Admin, Stock In', 'From TESTING, RENT, REPLACEMENT, ADV_REPLACEMENT, ON_APPROVAL, EMPTY, REFILL, or SCRAP list, return stock with location.', 'Return record, stock transaction, dated asset remark'],
  ['Faulty to scrap', 'Admin, Stock Out', 'Open faulty list, choose Scrap, enter location and remarks.', 'Scrap transaction, dated asset remark, timeline'],
  ['Transfer request - single', 'Admin, Stock Out', 'Choose an in-stock product and destination store. The request remains pending.', 'Transfer request and request item'],
  ['Transfer request - bulk', 'Admin, Stock Out', 'Upload barcode Excel and choose distinct source and destination stores.', 'Transfer request, request items, activity log'],
  ['Receive transfer - single', 'Admin, Stock In', 'Open pending request, approve an item, and enter destination location.', 'Transfer, stock-in transaction, received request item'],
  ['Receive transfer - bulk', 'Admin, Stock In', 'Select pending request, upload Barcode and Updated Location Excel. Unmatched barcodes remain pending.', 'Transfer history and request receipt details'],
  ['Audit and findings', 'Admin, Audit; Stock In attends findings', 'Audit a product or create a finding. Stock In records attendance action.', 'Audit record, finding, activity log'],
];
processes.getRange('A3:D13').format.borders = { preset: 'all', style: 'thin', color: border };
processes.getRange('A4:D13').format.wrapText = true;
processes.getRange('A:A').format.columnWidth = 27;
processes.getRange('B:B').format.columnWidth = 24;
processes.getRange('C:C').format.columnWidth = 60;
processes.getRange('D:D').format.columnWidth = 43;
processes.getRange('4:13').format.rowHeight = 46;
processes.freezePanes.freezeRows(3);

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(wb);
await output.save(`${outputDir}/inventory-operations-and-role-access.xlsx`);

for (const sheetName of ['Guide', 'Role Matrix', 'Processes']) {
  const preview = await wb.render({ sheetName, autoCrop: 'all', scale: 1, format: 'png' });
  await fs.writeFile(`${outputDir}/${sheetName.toLowerCase().replaceAll(' ', '-')}.png`, new Uint8Array(await preview.arrayBuffer()));
}
