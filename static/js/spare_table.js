/* ============================================================
   static/js/spare_table.js  (FIXED)

   KEY CHANGES:
   - Inline edit  → reads data-spare-id  (Spare model ID)
   - Stock Out    → reads data-id        (Product ID)
   - Audit        → reads data-id        (Product ID)
   - Audit History→ reads data-id        (Product ID)
============================================================ */

$(document).ready(function () {

    console.log("spare_table.js loaded");

    // ----------------------------------------
    // INIT DATATABLE
    // ----------------------------------------
    if ($.fn.DataTable.isDataTable('#spareTable')) {
        $('#spareTable').DataTable().destroy();
    }

    let table = $('#spareTable').DataTable({
        pageLength:    25,
        autoWidth:     false,
        orderCellsTop: true,
        fixedHeader:   false
    });

    setTimeout(function () {
        table.columns.adjust().draw();
    }, 200);


    // ----------------------------------------
    // COLUMN FILTER
    // ----------------------------------------
    $('#spareTable thead tr.filter-row th').each(function (i) {
        $('input', this).on('keyup change', function () {
            if (table.column(i).search() !== this.value) {
                table.column(i).search(this.value).draw();
            }
        });
    });


    // ----------------------------------------
    // INLINE EDIT
    // Uses data-spare-id (Spare model PK)
    // ----------------------------------------
    $('#spareTable tbody').on('click', '.editable-cell', function () {

        let cell = $(this);
        if (cell.find('input').length) return;

        let original = cell.text().trim();
        let input    = $('<input type="text" class="form-control form-control-sm">').val(original);

        cell.html(input);
        input.focus();

        input.on('keypress', function (e) {

            if (e.which === 13) {

                let value   = $(this).val();
                let field   = cell.data('field');
                // ✅ Use SPARE id for inline edit
                let spareId = cell.closest('tr').data('spare-id');

                $.ajax({
                    url:    '/spare/update/',
                    method: 'POST',
                    data: {
                        id:    spareId,
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
            }

        });

        input.on('blur', function () {
            cell.text(original);
        });

    });


    // ----------------------------------------
    // STOCK OUT — OPEN MODAL
    // Uses data-id (Product PK) ← FIXED
    // ----------------------------------------
    $(document).on('click', '.stockout-btn', function () {

        // ✅ Use PRODUCT id for stock out
        let productId = $(this).closest('tr').data('id');

        $('#stockOutProductId').val(productId);

        new bootstrap.Modal(document.getElementById('stockOutModal')).show();
    });


    // ----------------------------------------
    // STOCK OUT — SUBMIT
    // ----------------------------------------
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
                    row.fadeOut(300, function () {
                        table.row(row).remove().draw();
                    });
                    bootstrap.Modal.getInstance(
                        document.getElementById('stockOutModal')
                    ).hide();
                } else {
                    alert('Stock Out failed: ' + (res.error || 'Unknown error'));
                }

            },
            error: function (xhr) {
                console.error('Stock Out error:', xhr.status, xhr.responseText);
                alert('Server error (' + xhr.status + ') during stock out. Check console.');
            }
        });

    });


    // ----------------------------------------
    // AUDIT — OPEN MODAL
    // Uses data-id (Product PK) ← FIXED
    // ----------------------------------------
    $(document).on('click', '.audit-btn', function () {

        // ✅ Use PRODUCT id for audit
        let productId = $(this).closest('tr').data('id');

        $('#auditProductId').val(productId);
        $('#auditDate').val(new Date().toISOString().split('T')[0]);

        new bootstrap.Modal(document.getElementById('auditModal')).show();
    });


    // ----------------------------------------
    // AUDIT — SUBMIT
    // ----------------------------------------
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
                        .removeClass('btn-outline-info')
                        .addClass('btn-info');

                    bootstrap.Modal.getInstance(
                        document.getElementById('auditModal')
                    ).hide();

                    $('#auditRemark').val('');

                } else {
                    alert('Audit failed: ' + (res.error || 'Unknown error'));
                }

            },
            error: function (xhr) {
                console.error('Audit error:', xhr.status, xhr.responseText);
                alert('Server error (' + xhr.status + ') during audit. Check console.');
            }
        });

    });


    // ----------------------------------------
    // AUDIT HISTORY — OPEN MODAL
    // Uses data-id (Product PK) ← FIXED
    // ----------------------------------------
    $(document).on('click', '.audit-history-btn', function () {

        // ✅ Use PRODUCT id for audit history
        let productId = $(this).closest('tr').data('id');

        $.get(`/inventory/audit-history/${productId}/`, function (res) {

            let tbody = $('#auditHistoryTable tbody');
            tbody.empty();

            if (!res.data || res.data.length === 0) {
                tbody.append(
                    '<tr><td colspan="5" class="text-center text-muted py-3">' +
                    'No audit records found.</td></tr>'
                );
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

            new bootstrap.Modal(
                document.getElementById('auditHistoryModal')
            ).show();

        }).fail(function (xhr) {
            console.error('Audit history error:', xhr.status);
            alert('Could not load audit history.');
        });

    });

});


// ----------------------------------------
// CSRF TOKEN HELPER
// ----------------------------------------
function getCSRFToken() {
    return document.cookie.split('; ')
        .find(row => row.startsWith('csrftoken'))
        ?.split('=')[1];
}