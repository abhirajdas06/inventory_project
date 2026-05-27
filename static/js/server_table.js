/* ============================================================
   static/js/server_table.js  —  Server list page
   Handles:
     • DataTable + column filters
     • Inline edit (location, ref location, p-c location, remark)
     • View Components modal  (with OUT/sold highlighting)
     • Add Component modal    (AJAX multi-row)
     • Stock Out modal
     • Audit modal
     • Audit History modal
============================================================ */

$(document).ready(function () {

    console.log("server_table.js loaded");

    // ----------------------------------------
    // DATATABLE
    // ----------------------------------------
    if ($.fn.DataTable.isDataTable('#serverTable')) {
        $('#serverTable').DataTable().destroy();
    }

    let table = $('#serverTable').DataTable({
        pageLength:    25,
        autoWidth:     false,
        orderCellsTop: true,
        fixedHeader:   false
    });

    setTimeout(() => table.columns.adjust().draw(), 200);


    // ----------------------------------------
    // COLUMN FILTER
    // ----------------------------------------
    $('#serverTable thead tr.filter-row th').each(function (i) {
        $('input', this).on('keyup change', function () {
            if (table.column(i).search() !== this.value) {
                table.column(i).search(this.value).draw();
            }
        });
    });


    // ========================================
    // INLINE EDIT
    // ========================================
    $('#serverTable tbody').on('click', '.editable-cell', function () {

        let cell = $(this);
        if (cell.find('input').length) return;

        let original = cell.text().trim();
        let input    = $('<input type="text" class="form-control form-control-sm">').val(original);

        cell.html(input);
        input.focus();

        input.on('keypress', function (e) {
            if (e.which !== 13) return;

            let value   = $(this).val();
            let field   = cell.data('field');
            let serverId = cell.closest('tr').data('server-id');

            $.ajax({
                url:    '/servers/update/',
                method: 'POST',
                data: {
                    id:    serverId,
                    field: field,
                    value: value,
                    csrfmiddlewaretoken: getCSRFToken()
                },
                success: function () {
                    cell.text(value);
                    cell.css('background', '#d4edda');
                    setTimeout(() => cell.css('background', ''), 500);
                },
                error: function () {
                    cell.text(original);
                    alert('Update failed');
                }
            });
        });

        input.on('blur', function () { cell.text(original); });
    });


    // ========================================
    // VIEW COMPONENTS MODAL
    // ========================================
    $(document).on('click', '.view-components-btn', function () {

        let serverId = $(this).data('server-id');

        let body = $('#compDetailBody');
        body.html(
            '<tr><td colspan="16" class="text-center py-3">' +
            '<div class="spinner-border spinner-border-sm text-secondary"></div> Loading…' +
            '</td></tr>'
        );

        new bootstrap.Modal(document.getElementById('viewComponentsModal')).show();

        $.get(`/servers/components/${serverId}/`, function (res) {

            body.empty();

            if (!res.components || res.components.length === 0) {
                body.html('<tr><td colspan="16" class="text-center text-muted py-3">No components.</td></tr>');
                return;
            }

            // update modal title
            $('#viewCompModalTitle').text(`Components — ${res.server_model || ''}`);

            let total = res.components.length;
            let sold  = res.components.filter(c => c.is_out).length;
            $('#viewCompSummary').text(`${total} total · ${sold} sold`);

            res.components.forEach(c => {

                let isOut     = c.is_out;
                let rowClass  = isOut ? 'comp-out-row' : 'comp-in-row';

                let serialCell = isOut
                    ? `<code class="text-danger">${c.serial_no}</code><span class="sold-tag">SOLD</span>`
                    : `<code>${c.serial_no}</code>`;

                let statusBadge = isOut
                    ? `<span class="badge bg-danger">OUT</span>`
                    : `<span class="badge bg-success">${c.status}</span>`;

                // category table pill
                let tablePill = `<span class="badge bg-light text-dark border" style="font-size:10px;">${c.category_table || 'spare'}</span>`;

                body.append(`
                    <tr class="${rowClass}">
                        <td><span class="badge bg-secondary">${c.spare_type}</span></td>
                        <td>${tablePill}</td>
                        <td>${c.part_no}</td>
                        <td>${c.alt_part_no}</td>
                        <td>${serialCell}</td>
                        <td>${c.alt_serial_no}</td>
                        <td>${c.specs}</td>
                        <td>${c.barcode}</td>
                        <td>${c.qty}</td>
                        <td>
                            <span class="badge ${c.working_status === 'WORKING' ? 'bg-success' : 'bg-danger'}">
                                ${c.working_status}
                            </span>
                        </td>
                        <td>${c.location}</td>
                        <td>${c.store}</td>
                        <td>${statusBadge}</td>
                        <td>${isOut ? `<span class="text-danger fw-semibold">${c.client}</span>` : '-'}</td>
                        <td>${isOut ? `<span class="text-danger fw-semibold">${c.invoice}</span>` : '-'}</td>
                        <td>${isOut ? `<span class="text-danger">${c.out_date}</span>` : '-'}</td>
                    </tr>
                `);
            });

        }).fail(function () {
            body.html('<tr><td colspan="16" class="text-center text-danger py-3">Failed to load.</td></tr>');
        });

    });


    // ========================================
    // ADD COMPONENT MODAL — OPEN
    // ========================================
    $(document).on('click', '.add-component-btn', function () {

        let serverId = $(this).data('server-id');
        $('#addCompServerId').val(serverId);

        // reset table to one empty row
        let tbody    = document.getElementById('addCompRows');
        let firstRow = tbody.querySelector('tr').cloneNode(true);
        firstRow.querySelectorAll('input').forEach(inp => {
            inp.value = '';
            inp.classList.remove('error');
        });
        firstRow.querySelectorAll('select').forEach(sel => sel.selectedIndex = 0);
        let qty = firstRow.querySelector("input[name='comp_qty[]']");
        if (qty) qty.value = 1;
        tbody.innerHTML = '';
        tbody.appendChild(firstRow);

        $('#addCompAlert').addClass('d-none').text('');

        new bootstrap.Modal(document.getElementById('addComponentModal')).show();
    });


    // ========================================
    // ADD COMPONENT MODAL — ADD / REMOVE ROWS
    // ========================================
    $(document).on('click', '.add-comp-row-btn', function () {

        let tbody    = document.getElementById('addCompRows');
        let firstRow = tbody.querySelector('tr');
        let newRow   = firstRow.cloneNode(true);

        newRow.querySelectorAll('input').forEach(inp => {
            inp.value = '';
            inp.classList.remove('error');
        });
        newRow.querySelectorAll('select').forEach(sel => sel.selectedIndex = 0);
        newRow.querySelectorAll('.serial-error, .barcode-error').forEach(el => el.remove());

        let qty = newRow.querySelector("input[name='comp_qty[]']");
        if (qty) qty.value = 1;

        tbody.appendChild(newRow);
    });

    $(document).on('click', '.remove-add-comp', function () {
        let rows = document.querySelectorAll('#addCompRows tr');
        if (rows.length > 1) {
            this.closest('tr').remove();
        }
    });


    // ========================================
    // ADD COMPONENT MODAL — SAVE
    // ========================================
    $(document).on('click', '#saveAddComp', function () {

        let serverId = $('#addCompServerId').val();
        let alertEl  = $('#addCompAlert');
        let saveBtn  = $(this);

        // client-side: check for server-detected duplicate barcodes
        let valid    = true;
        let barcodes = [];

        $('#addCompTable .barcode-check').each(function () {
            let val = $(this).val().trim().toUpperCase();
            $(this).val(val);

            if (!val) return;

            if ($(this).hasClass('error')) {
                valid = false;
            }

            if (barcodes.includes(val)) {
                alertEl.removeClass('d-none alert-success').addClass('alert-danger')
                       .text('Duplicate barcode in form: ' + val);
                valid = false;
                return false;
            }

            barcodes.push(val);
        });

        if (!valid) return;

        // build form data
        let formData = new FormData();
        formData.append('server_id', serverId);
        formData.append('csrfmiddlewaretoken', getCSRFToken());

        let compFields = [
            'comp_spare_type', 'comp_brand', 'comp_model',
            'comp_part_no', 'comp_alt_part_no',
            'comp_serial_no', 'comp_alt_serial_no',
            'comp_specs', 'comp_barcode', 'comp_qty',
            'comp_working_status', 'comp_location',
            'comp_reference_location', 'comp_parent_child_location',
            'comp_remark'
        ];

        $('#addCompTable tbody tr').each(function () {
            compFields.forEach(f => {
                let el = $(this).find(`[name="${f}[]"]`);
                formData.append(f + '[]', el.val() || '');
            });
        });

        saveBtn.prop('disabled', true).text('Saving…');

        $.ajax({
            url:         '/servers/add-component/',
            method:      'POST',
            data:        formData,
            processData: false,
            contentType: false,
            success: function (res) {

                saveBtn.prop('disabled', false).text('Save Components');

                if (res.success) {

                    alertEl.removeClass('d-none alert-danger').addClass('alert-success')
                           .text(`✓ ${res.added} component(s) added successfully.`);

                    // update component count button
                    let row = $(`tr[data-server-id="${serverId}"]`);
                    let btn = row.find('.view-components-btn');
                    let cur = parseInt(btn.text()) || 0;
                    let newCount = cur + res.added;
                    btn.html(`<i class="bi bi-grid me-1"></i>${newCount} item${newCount !== 1 ? 's' : ''}`);

                    setTimeout(() => {
                        bootstrap.Modal.getInstance(
                            document.getElementById('addComponentModal')
                        ).hide();
                    }, 1400);

                } else {
                    alertEl.removeClass('d-none alert-success').addClass('alert-danger')
                           .text('Error: ' + (res.error || 'Unknown error'));
                }
            },
            error: function () {
                saveBtn.prop('disabled', false).text('Save Components');
                alertEl.removeClass('d-none alert-success').addClass('alert-danger')
                       .text('Server error. Please try again.');
            }
        });

    });


    // ========================================
    // STOCK OUT — OPEN
    // ========================================
    $(document).on('click', '.stockout-btn', function () {
        let productId = $(this).closest('tr').data('id');
        $('#stockOutProductId').val(productId);
        new bootstrap.Modal(document.getElementById('stockOutModal')).show();
    });


    // ========================================
    // STOCK OUT — SUBMIT
    // ========================================
    $(document).on('click', '#saveStockOut', function () {

        let productId = $('#stockOutProductId').val();

        let data = {
            product_id:     productId,
            client_name:    $('#stockOutClient').val(),
            invoice_no:     $('#stockOutInvoice').val(),
            stock_status:   $('#stockOutStatus').val(),
            stock_out_date: $('#stockOutDate').val(),
            csrfmiddlewaretoken: getCSRFToken()
        };

        $.ajax({
            url:    '/inventory/stock-out/',
            method: 'POST',
            data:   data,
            success: function (res) {
                if (res.success) {
                    let row = $(`tr[data-id="${productId}"]`);
                    row.fadeOut(300, () => table.row(row).remove().draw());
                    bootstrap.Modal.getInstance(
                        document.getElementById('stockOutModal')
                    ).hide();
                } else {
                    alert('Stock Out failed.');
                }
            },
            error: function () { alert('Server error during stock out.'); }
        });
    });


    // ========================================
    // AUDIT — OPEN
    // ========================================
    $(document).on('click', '.audit-btn', function () {
        let productId = $(this).closest('tr').data('id');
        $('#auditProductId').val(productId);
        $('#auditDate').val(new Date().toISOString().split('T')[0]);
        new bootstrap.Modal(document.getElementById('auditModal')).show();
    });


    // ========================================
    // AUDIT — SUBMIT
    // ========================================
    $(document).on('click', '#saveAudit', function () {

        let productId = $('#auditProductId').val();

        let data = {
            product_id:   productId,
            audit_remark: $('#auditRemark').val(),
            audited_on:   $('#auditDate').val(),
            csrfmiddlewaretoken: getCSRFToken()
        };

        $.ajax({
            url:    '/inventory/audit/',
            method: 'POST',
            data:   data,
            success: function (res) {
                if (res.success) {
                    $(`tr[data-id="${productId}"]`)
                        .find('.audit-history-btn')
                        .text(data.audited_on || 'View')
                        .removeClass('btn-outline-info').addClass('btn-info');
                    bootstrap.Modal.getInstance(
                        document.getElementById('auditModal')
                    ).hide();
                    $('#auditRemark').val('');
                } else {
                    alert('Audit failed.');
                }
            },
            error: function () { alert('Server error during audit.'); }
        });
    });


    // ========================================
    // AUDIT HISTORY
    // ========================================
    $(document).on('click', '.audit-history-btn', function () {

        let productId = $(this).closest('tr').data('id');

        $.get(`/inventory/audit-history/${productId}/`, function (res) {

            let tbody = $('#auditHistoryTable tbody');
            tbody.empty();

            if (!res.data || res.data.length === 0) {
                tbody.html('<tr><td colspan="5" class="text-center text-muted py-3">No audit records.</td></tr>');
            } else {
                res.data.forEach(item => {
                    tbody.append(`
                        <tr>
                            <td>${item.date     || '-'}</td>
                            <td>${item.user     || '-'}</td>
                            <td>${item.location || '-'}</td>
                            <td>${item.status   || '-'}</td>
                            <td>${item.remark   || '-'}</td>
                        </tr>
                    `);
                });
            }

            new bootstrap.Modal(document.getElementById('auditHistoryModal')).show();

        }).fail(() => alert('Could not load audit history.'));
    });

});


// ----------------------------------------
// CSRF HELPER
// ----------------------------------------
function getCSRFToken() {
    return document.cookie.split('; ')
        .find(r => r.startsWith('csrftoken'))
        ?.split('=')[1];
}