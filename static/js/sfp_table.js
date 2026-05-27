/* ============================================================
   static/js/sfp_table.js  —  SFP list page
============================================================ */

$(document).ready(function () {

    console.log("sfp_table.js loaded");

    // ----------------------------------------
    // INIT DATATABLE
    // ----------------------------------------
    if ($.fn.DataTable.isDataTable('#sfpTable')) {
        $('#sfpTable').DataTable().destroy();
    }

    let table = $('#sfpTable').DataTable({
        pageLength: 25,
        scrollX: true,
        autoWidth: false,          // IMPORTANT for alignment
        orderCellsTop: true,
        fixedHeader: true,
        deferRender: true
    });

    setTimeout(function () {
        table.columns.adjust().draw();
    }, 200);


    // ----------------------------------------
    // COLUMN FILTER
    // ----------------------------------------
    $('#sfpTable thead tr.filter-row th').each(function (i) {
        $('input', this).on('keyup change', function () {
            if (table.column(i).search() !== this.value) {
                table.column(i).search(this.value).draw();
            }
        });
    });


    // ----------------------------------------
    // INLINE EDIT
    // ----------------------------------------
    $('#sfpTable tbody').on('click', '.editable-cell', function () {

        let cell = $(this);
        if (cell.find('input').length) return;

        let original = cell.text().trim();
        let input    = $('<input type="text" class="form-control form-control-sm">').val(original);

        cell.html(input);
        input.focus();

        input.on('keypress', function (e) {

            if (e.which === 13) {

                let value = $(this).val();
                let field = cell.data('field');
                let sfpId = cell.closest('tr').data('sfp-id');

                $.ajax({
                    url:    '/sfp/update/',
                    method: 'POST',
                    data: {
                        id:    sfpId,
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
    // ----------------------------------------
    $(document).on('click', '.stockout-btn', function () {
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
                    alert('Stock Out failed. Please try again.');
                }
            },
            error: function () {
                alert('Server error during stock out.');
            }
        });

    });


    // ----------------------------------------
    // AUDIT — OPEN MODAL
    // ----------------------------------------
    $(document).on('click', '.audit-btn', function () {
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
                    alert('Audit failed. Please try again.');
                }
            },
            error: function () {
                alert('Server error during audit.');
            }
        });

    });


    // ----------------------------------------
    // AUDIT HISTORY — OPEN MODAL
    // ----------------------------------------
    $(document).on('click', '.audit-history-btn', function () {

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

        }).fail(function () {
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