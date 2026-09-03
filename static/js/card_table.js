$(document).ready(function () {

    // =============================
    // 🔥 INIT DATATABLE
    // =============================
    if ($.fn.DataTable.isDataTable('#cardTable')) {
        $('#cardTable').DataTable().destroy();
    }

    let table = $('#cardTable').DataTable({
        pageLength: 25,
        scrollX: true,
        autoWidth: false,          // IMPORTANT for alignment
        orderCellsTop: true,
        fixedHeader: true,
        deferRender: true, paging: false, searching: false, info: false
    });

    // =============================
    // 🔥 COLUMN FILTER
    // =============================
    $('#cardTable thead').on('keyup change', 'input', function () {
        let index = $(this).parent().index();
        table.column(index).search(this.value).draw();
    });


    // =============================
    // 🔥 INLINE EDIT
    // =============================
    $('#cardTable tbody').on('click', '.editable-cell', function () {

        let cell = $(this);

        if (cell.find('input').length) return;

        let original = cell.text().trim();

        let input = $('<input type="text" class="form-control form-control-sm">')
            .val(original);

        cell.html(input);
        input.focus();

        input.on('keypress', function (e) {

            if (e.which === 13) {

                let value = $(this).val();
                let field = cell.data('field');
                let id = cell.closest('tr').data('card-id');

                $.ajax({
                    url: "/spare/update/",
                    method: "POST",
                    data: {
                        id: id,
                        model: 'card',
                        field: field,
                        value: value,
                        csrfmiddlewaretoken: getCSRFToken()
                    },
                    success: function () {
                        cell.text(value);
                    },
                    error: function () {
                        cell.text(original);
                        alert("Update failed");
                    }
                });

            }

        });

        input.on('blur', function () {
            cell.text(original);
        });

    });


    // =============================
    // 🔥 STOCK OUT MODAL OPEN
    // =============================
    $(document).on('click', '.stockout-btn', function () {

        let row = $(this).closest('tr');
        let product_id = row.data('id');

        $('#stockOutProductId').val(product_id);

        let modal = new bootstrap.Modal(document.getElementById('stockOutModal'));
        modal.show();
    });


    // =============================
    // 🔥 AUDIT MODAL OPEN
    // =============================
    $(document).on('click', '.audit-btn', function () {

        let row = $(this).closest('tr');
        let product_id = row.data('id');

        $('#auditProductId').val(product_id);

        let modal = new bootstrap.Modal(document.getElementById('auditModal'));
        modal.show();
    });


    // =============================
    // 🔥 STOCK OUT SUBMIT
    // =============================
    $(document).on('click', '#saveStockOut', function () {

        let data = {
            product_id: $('#stockOutProductId').val(),
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

                    let row = $(`tr[data-id="${data.product_id}"]`);
                    row.fadeOut(200);

                    bootstrap.Modal.getInstance(
                        document.getElementById('stockOutModal')
                    ).hide();

                } else {
                    alert("Stock Out Failed");
                }

            },
            error: function () {
                alert("Server error during stock out");
            }
        });

    });


    // =============================
    // 🔥 AUDIT SUBMIT
    // =============================
    $(document).on('click', '#saveAudit', function () {

        let data = {
            product_id: $('#auditProductId').val(),
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

                    bootstrap.Modal.getInstance(
                        document.getElementById('auditModal')
                    ).hide();

                    alert("Audit saved successfully");

                } else {
                    alert("Audit failed");
                }

            },
            error: function () {
                alert("Server error during audit");
            }
        });

    });


    // =============================
    // 🔥 AUDIT HISTORY
    // =============================
    $(document).on('click', '.audit-history-btn', function () {

        let row = $(this).closest('tr');
        let product_id = row.data('id');

        $.get(`/inventory/audit-history/${product_id}/`, function (res) {

            let tbody = $("#auditHistoryTable tbody");
            tbody.empty();

            res.data.forEach(item => {
                tbody.append(`
                    <tr>
                        <td>${item.date || ''}</td>
                        <td>${item.user || ''}</td>
                        <td>${item.location || ''}</td>
                        <td>${item.status || ''}</td>
                        <td>${item.audit_result || ''}</td>
                        <td>${item.remark || ''}</td>
                    </tr>
                `);
            });

            let modal = new bootstrap.Modal(
                document.getElementById('auditHistoryModal')
            );

            modal.show();
        });

    });

});


// =============================
// 🔥 CSRF TOKEN
// =============================
function getCSRFToken() {
    return document.cookie.split('; ')
        .find(row => row.startsWith('csrftoken'))
        ?.split('=')[1];
}
