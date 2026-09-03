

 /* ============================================================
   static/js/controller_table.js
   Full replacement — includes:
     • DataTable + column filters
     • Inline edit
     • Components modal  (with OUT highlighting + client/invoice)
     • Add component modal (AJAX multi-row)
     • Stock Out modal
     • Audit modal
     • Audit History modal
============================================================ */

$(document).ready(function () {

    // ----------------------------------------
    // DATATABLE
    // ----------------------------------------
    if ($.fn.DataTable.isDataTable('#controllerTable')) {
        $('#controllerTable').DataTable().destroy();
    }

    let table = $('#controllerTable').DataTable({
        pageLength: 25,
        scrollX: true,
        autoWidth: false,          // IMPORTANT for alignment
        orderCellsTop: true,
        fixedHeader: true,
        deferRender: true, paging: false, searching: false, info: false
    });

    setTimeout(() => table.columns.adjust().draw(), 200);


    // ----------------------------------------
    // COLUMN FILTER
    // ----------------------------------------
    $('#controllerTable thead tr.filter-row th').each(function (i) {
        $('input', this).on('keyup change', function () {
            if (table.column(i).search() !== this.value) {
                table.column(i).search(this.value).draw();
            }
        });
    });


    // ----------------------------------------
    // INLINE EDIT
    // ----------------------------------------
    $('#controllerTable tbody').on('click', '.editable-cell', function () {

        let cell = $(this);
        if (cell.find('input').length) return;

        let original = cell.text().trim();
        let input    = $('<input type="text" class="form-control form-control-sm">').val(original);

        cell.html(input);
        input.focus();

        input.on('keypress', function (e) {
            if (e.which !== 13) return;

            let value  = $(this).val();
            let field  = cell.data('field');
            let ctrlId = cell.closest('tr').data('ctrl-id');

            $.ajax({
                url:    '/spare/controller-update/',
                method: 'POST',
                data: {
                    id: ctrlId, field: field, value: value,
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


    // ============================================================
    // COMPONENTS VIEW MODAL
    // ============================================================

    $(document).on('click', '.components-btn', function () {

        let ctrlId = $(this).data('ctrl-id');

        // show loading state
        let tbody = $('#componentsDetailTable tbody');
        tbody.html(
            '<tr><td colspan="12" class="text-center py-3">' +
            '<div class="spinner-border spinner-border-sm text-secondary"></div>' +
            ' Loading…</td></tr>'
        );

        new bootstrap.Modal(document.getElementById('componentsModal')).show();

        $.get(`/spare/controller-components/${ctrlId}/`, function (res) {

            tbody.empty();

            if (!res.components || res.components.length === 0) {
                tbody.html(
                    '<tr><td colspan="12" class="text-center text-muted py-3">' +
                    'No components found.</td></tr>'
                );
                return;
            }

            res.components.forEach(c => {

                let isOut    = c.is_out;
                let rowClass = isOut ? 'comp-row-out' : 'comp-row-in';

                // status badge
                let statusBadge = isOut
                    ? `<span class="badge bg-danger">OUT</span>`
                    : `<span class="badge bg-success">${c.status}</span>`;

                // out info columns
                let clientCell  = isOut ? `<span class="text-danger fw-semibold">${c.client  || '-'}</span>` : '-';
                let invoiceCell = isOut ? `<span class="text-danger fw-semibold">${c.invoice || '-'}</span>` : '-';
                let outDateCell = isOut ? `<span class="text-danger">${c.out_date || '-'}</span>` : '-';

                tbody.append(`
                    <tr class="${rowClass}">
                        <td>
                            <span class="badge bg-secondary">${c.category}</span>
                        </td>
                        <td>${c.brand}</td>
                        <td>${c.model}</td>
                        <td>${c.part_no}</td>
                        <td>
                            <code class="${isOut ? 'text-danger' : ''}">${c.serial_no}</code>
                            ${isOut ? '<span class="sold-badge ms-1">SOLD</span>' : ''}
                        </td>
                        <td>${c.specs}</td>
                        <td>${c.barcode}</td>
                        <td>${c.store}</td>
                        <td>${statusBadge}</td>
                        <td>${clientCell}</td>
                        <td>${invoiceCell}</td>
                        <td>${outDateCell}</td>
                    </tr>
                `);
            });

            // update modal subtitle with serial
            let row = $(`tr[data-ctrl-id="${ctrlId}"]`).first().closest('tr');

        }).fail(function () {
            tbody.html(
                '<tr><td colspan="12" class="text-center text-danger py-3">' +
                'Failed to load components.</td></tr>'
            );
        });

    });


    // ============================================================
    // ADD COMPONENT MODAL — OPEN
    // ============================================================

    $(document).on('click', '.add-component-list-btn', function () {

        let ctrlId = $(this).data('ctrl-id');

        $('#addCompControllerId').val(ctrlId);

        // reset the table to a single empty row
        let tbody = document.getElementById('addCompRows');
        let firstRow = tbody.querySelector('tr').cloneNode(true);
        firstRow.querySelectorAll('input').forEach(inp => {
            inp.value = '';
            inp.classList.remove('error');
        });
        firstRow.querySelectorAll('select').forEach(sel => sel.selectedIndex = 0);
        tbody.innerHTML = '';
        tbody.appendChild(firstRow);

        // clear alert
        $('#addCompAlert').addClass('d-none').text('');

        new bootstrap.Modal(document.getElementById('addComponentModal')).show();
    });


    // ============================================================
    // ADD COMPONENT MODAL — ADD / REMOVE ROWS
    // ============================================================

    $(document).on('click', '.add-comp-row-btn', function () {

        let tbody    = document.getElementById('addCompRows');
        let firstRow = tbody.querySelector('tr');
        let newRow   = firstRow.cloneNode(true);

        newRow.querySelectorAll('input').forEach(inp => {
            inp.value = '';
            inp.classList.remove('error');
        });
        newRow.querySelectorAll('.serial-error').forEach(el => el.remove());

        let qty = newRow.querySelector("input[name='comp_qty[]']");
        if (qty) qty.value = 1;

        tbody.appendChild(newRow);
    });

    $(document).on('click', '.remove-comp-row', function () {
        let rows = document.querySelectorAll('#addCompRows tr');
        if (rows.length > 1) {
            this.closest('tr').remove();
        }
    });


    // ============================================================
    // ADD COMPONENT MODAL — SERIAL CHECK
    // ============================================================

    let compSerialDebounce;

    $(document).on('blur', '.new-comp-serial', function () {

        clearTimeout(compSerialDebounce);

        let input  = $(this);
        let serial = input.val().trim().toUpperCase();
        input.val(serial);

        input.removeClass('error');
        input.parent().find('.serial-error').remove();

        if (!serial) return;

        compSerialDebounce = setTimeout(() => {

            $.get(`/spare/check-serial/?serial_no=${encodeURIComponent(serial)}`, function (data) {
                if (data.exists) {
                    input.addClass('error');
                    input.parent().append(
                        '<div class="serial-error">Duplicate serial</div>'
                    );
                }
            });

        }, 300);

    });


    // ============================================================
    // ADD COMPONENT MODAL — SAVE
    // ============================================================

    $(document).on('click', '#saveNewComponents', function () {

        let controllerId = $('#addCompControllerId').val();
        let alertEl      = $('#addCompAlert');

        // client-side validation — require at least one serial
        let serials = [];
        let valid   = true;

        $('.new-comp-serial').each(function () {
            let val = $(this).val().trim().toUpperCase();
            $(this).val(val);

            if (val) {
                if (serials.includes(val)) {
                    alertEl.removeClass('d-none alert-success')
                           .addClass('alert-danger')
                           .text('Duplicate serial in form: ' + val);
                    valid = false;
                    return false;
                }
                serials.push(val);
            }

            if ($(this).hasClass('error')) {
                valid = false;
            }
        });

        if (!valid) return;

        if (serials.length === 0) {
            alertEl.removeClass('d-none alert-success')
                   .addClass('alert-danger')
                   .text('Please enter at least one serial number.');
            return;
        }

        // build FormData from the modal table
        let formData = new FormData();
        formData.append('controller_id', controllerId);
        formData.append('csrfmiddlewaretoken', getCSRFToken());

        $('#addComponentTable tbody tr').each(function () {

            let fields = [
                'comp_spare_type', 'comp_product_name', 'comp_brand', 'comp_model',
                'comp_part_no', 'comp_alt_part_no', 'comp_serial_no',
                'comp_alt_serial_no', 'comp_specs', 'comp_qty',
                'comp_barcode', 'comp_remark'
            ];

            fields.forEach(f => {
                let el = $(this).find(`[name="${f}[]"]`);
                formData.append(f + '[]', el.val() || '');
            });
        });

        // disable button while saving
        let saveBtn = $('#saveNewComponents');
        saveBtn.prop('disabled', true).text('Saving…');

        $.ajax({
            url:         '/spare/controller-add-component/',
            method:      'POST',
            data:        formData,
            processData: false,
            contentType: false,
            success: function (res) {

                saveBtn.prop('disabled', false).text('Save Components');

                if (res.success) {

                    alertEl.removeClass('d-none alert-danger')
                           .addClass('alert-success')
                           .text(`✓ ${res.added} component(s) added successfully.`);

                    // update the count button in the table
                    let row = $(`tr[data-ctrl-id="${controllerId}"]`);
                    let btn = row.find('.components-btn');
                    let current = parseInt(btn.text()) || 0;
                    btn.text((current + res.added) + ' item' + (current + res.added !== 1 ? 's' : ''));

                    // auto close modal after 1.5s
                    setTimeout(() => {
                        bootstrap.Modal.getInstance(
                            document.getElementById('addComponentModal')
                        ).hide();
                    }, 1500);

                } else {
                    alertEl.removeClass('d-none alert-success')
                           .addClass('alert-danger')
                           .text('Error: ' + (res.error || 'Unknown error'));
                }

            },
            error: function () {
                saveBtn.prop('disabled', false).text('Save Components');
                alertEl.removeClass('d-none alert-success')
                       .addClass('alert-danger')
                       .text('Server error. Please try again.');
            }
        });

    });


    // ============================================================
    // STOCK OUT
    // ============================================================

    $(document).on('click', '.stockout-btn', function () {
        let productId = $(this).closest('tr').data('id');
        $('#stockOutProductId').val(productId);
        new bootstrap.Modal(document.getElementById('stockOutModal')).show();
    });

    $(document).on('click', '#saveStockOut', function () {

        let productId = $('#stockOutProductId').val();

        let data = {
            product_id:     productId,
            client_name:    $('#stockOutClient').val(),
            invoice_no:     $('#stockOutInvoice').val(),
            olf_dc_number:     $('#stockOutOlfDc').val(),
            stock_status:   $('#stockOutStatus').val(),
            stock_out_date: $('#stockOutDate').val(),
            expected_return_date: $('#stockOutReturnDate').val(),
            csrfmiddlewaretoken: getCSRFToken()
        };

        $.ajax({
            url: '/inventory/stock-out/', method: 'POST', data: data,
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
            error: function () { alert('Server error.'); }
        });
    });


    // ============================================================
    // AUDIT
    // ============================================================

    $(document).on('click', '.audit-btn', function () {
        let productId = $(this).closest('tr').data('id');
        $('#auditProductId').val(productId);
        $('#auditDate').val(new Date().toISOString().split('T')[0]);
        new bootstrap.Modal(document.getElementById('auditModal')).show();
    });

    $(document).on('click', '#saveAudit', function () {

        let productId = $('#auditProductId').val();
        let data = {
            product_id:   productId,
            audit_remark: $('#auditRemark').val(),
            audited_on:   $('#auditDate').val(),
            audit_result:   $('#auditResult').val(),
            csrfmiddlewaretoken: getCSRFToken()
        };

        $.ajax({
            url: '/inventory/audit/', method: 'POST', data: data,
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
            error: function () { alert('Server error.'); }
        });
    });


    // ============================================================
    // AUDIT HISTORY
    // ============================================================

    $(document).on('click', '.audit-history-btn', function () {

        let productId = $(this).closest('tr').data('id');

        $.get(`/inventory/audit-history/${productId}/`, function (res) {

            let tbody = $('#auditHistoryTable tbody');
            tbody.empty();

            if (!res.data || res.data.length === 0) {
                tbody.html('<tr><td colspan="6" class="text-center text-muted py-3">No audit records.</td></tr>');
            } else {
                res.data.forEach(item => {
                    tbody.append(`
                        <tr>
                            <td>${item.date     || '-'}</td>
                            <td>${item.user     || '-'}</td>
                            <td>${item.location || '-'}</td>
                            <td>${item.status   || '-'}</td>
                            <td>${item.audit_result || '-'}</td>
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

