$(document).ready(function () {

    // =============================
    // INIT DATATABLE
    // =============================
    if ($.fn.DataTable.isDataTable('#cpuTable')) {
        $('#cpuTable').DataTable().destroy();
    }

    let table = $('#cpuTable').DataTable({
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


    // =============================
    // COLUMN FILTER
    // =============================
    $('#cpuTable thead tr.filter-row th').each(function (i) {
        $('input', this).on('keyup change', function () {
            if (table.column(i).search() !== this.value) {
                table.column(i).search(this.value).draw();
            }
        });
    });


    // =============================
    // INLINE EDIT
    // =============================
    $('#cpuTable tbody').on('click', '.editable-cell', function () {

        let cell = $(this);

        if (cell.find('input').length) return;

        let original = cell.text().trim();

        let input = $('<input type="text" class="form-control form-control-sm">')
            .val(original);

        cell.html(input);
        input.focus();

        // SAVE ON ENTER
        input.on('keypress', function (e) {

            if (e.which === 13) {

                let value = $(this).val();
                let field = cell.data('field');
                let spareId = cell.closest('tr').data('spare-id');

                $.ajax({
                    url: '/spare/cpu-update/',
                    method: 'POST',
                    data: {
                        id: spareId,
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

        // CANCEL ON BLUR
        input.on('blur', function () {
            cell.text(original);
        });

    });


    // =============================
    // STOCK OUT — OPEN MODAL
    // =============================
    $(document).on('click', '.stockout-btn', function () {

        let row = $(this).closest('tr');
        let product_id = row.data('id');

        $('#stockOutProductId').val(product_id);

        let modal = new bootstrap.Modal(document.getElementById('stockOutModal'));
        modal.show();
    });


    // =============================
    // STOCK OUT — SUBMIT
    // =============================
    $(document).on('click', '#saveStockOut', function () {

        let product_id = $('#stockOutProductId').val();

        let data = {
            product_id: product_id,
            client_name: $('#stockOutClient').val(),
            invoice_no: $('#stockOutInvoice').val(),
            olf_dc_number: $('#stockOutOlfDc').val(),
            stock_status: $('#stockOutStatus').val(),
            stock_out_date: $('#stockOutDate').val(),
            expected_return_date: $('#stockOutReturnDate').val(),
            csrfmiddlewaretoken: getCSRFToken()
        };

        $.ajax({
            url: '/inventory/stock-out/',
            method: 'POST',
            data: data,
            success: function (res) {

                if (res.success) {
                    // remove row from table (item is now OUT)
                    let row = $(`tr[data-id="${product_id}"]`);
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


    // =============================
    // AUDIT — OPEN MODAL
    // =============================
    $(document).on('click', '.audit-btn', function () {

        let row = $(this).closest('tr');
        let product_id = row.data('id');

        $('#auditProductId').val(product_id);

        // set today's date as default
        let today = new Date().toISOString().split('T')[0];
        $('#auditDate').val(today);

        let modal = new bootstrap.Modal(document.getElementById('auditModal'));
        modal.show();
    });


    // =============================
    // AUDIT — SUBMIT
    // =============================
    $(document).on('click', '#saveAudit', function () {

        let product_id = $('#auditProductId').val();

        let data = {
            product_id: product_id,
            audit_remark: $('#auditRemark').val(),
            audited_on: $('#auditDate').val(),
            audit_result: $('#auditResult').val(),
            csrfmiddlewaretoken: getCSRFToken()
        };

        $.ajax({
            url: '/inventory/audit/',
            method: 'POST',
            data: data,
            success: function (res) {

                if (res.success) {

                    // update last audit date in the row
                    let row = $(`tr[data-id="${product_id}"]`);
                    let auditBtn = row.find('.audit-history-btn');
                    auditBtn.text(data.audited_on || 'View');
                    auditBtn.addClass('btn-info').removeClass('btn-outline-info');

                    bootstrap.Modal.getInstance(
                        document.getElementById('auditModal')
                    ).hide();

                    // clear remark for next use
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


    // =============================
    // AUDIT HISTORY — OPEN MODAL
    // =============================
    $(document).on('click', '.audit-history-btn', function () {

        let row = $(this).closest('tr');
        let product_id = row.data('id');

        $.get(`/inventory/audit-history/${product_id}/`, function (res) {

            let tbody = $('#auditHistoryTable tbody');
            tbody.empty();

            if (res.data.length === 0) {
                tbody.append('<tr><td colspan="6" class="text-center text-muted">No audit records found.</td></tr>');
            } else {
                res.data.forEach(item => {
                    tbody.append(`
                        <tr>
                            <td>${item.date || '-'}</td>
                            <td>${item.user || '-'}</td>
                            <td>${item.location || '-'}</td>
                            <td>${item.status || '-'}</td>
                            <td>${item.audit_result || '-'}</td>
                            <td>${item.remark || '-'}</td>
                        </tr>
                    `);
                });
            }

            let modal = new bootstrap.Modal(
                document.getElementById('auditHistoryModal')
            );
            modal.show();

        }).fail(function () {
            alert('Could not load audit history.');
        });

    });

});


// =============================
// CSRF TOKEN
// =============================
function getCSRFToken() {
    return document.cookie.split('; ')
        .find(row => row.startsWith('csrftoken'))
        ?.split('=')[1];
}
