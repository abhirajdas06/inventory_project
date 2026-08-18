/* ============================================================
   static/js/spare.js  —  Add Spare page
============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    // ----------------------------------------
    // ADD ROW
    // ----------------------------------------
    document.addEventListener("click", function (e) {

        if (!e.target.closest(".add-row")) return;

        let tbody    = document.querySelector("#spareTable tbody");
        let firstRow = tbody.querySelector("tr");
        let newRow   = firstRow.cloneNode(true);

        newRow.querySelectorAll("input").forEach(input => {
            if (input.hasAttribute("readonly")) return;
            input.value = "";
            input.classList.remove("error");
        });

        newRow.querySelectorAll("select").forEach(sel => {
            sel.selectedIndex = 0;
        });

        let qty = newRow.querySelector("input[name='qty[]']");
        if (qty) qty.value = 1;

        newRow.querySelectorAll(".serial-error, .barcode-error").forEach(el => el.remove());

        tbody.appendChild(newRow);
    });


    // ----------------------------------------
    // REMOVE ROW
    // ----------------------------------------
    document.addEventListener("click", function (e) {

        let removeBtn = e.target.closest(".remove");
        if (!removeBtn) return;

        let rows = document.querySelectorAll("#spareTable tbody tr");
        if (rows.length > 1) {
            removeBtn.closest("tr").remove();
        }
    });


    // ----------------------------------------
    // FORM VALIDATION
    // ----------------------------------------
    let form = document.getElementById("spareForm");

    if (form) {
        form.addEventListener("submit", function (e) {

            let valid    = true;
            let barcodes = [];

            document.querySelectorAll(".barcode-check").forEach(input => {

                let val = input.value.trim().toUpperCase();
                input.value = val;

                if (!val) return;

                if (input.classList.contains("error")) {
                    valid = false;
                }

                if (barcodes.includes(val)) {
                    alert("Duplicate barcode in form: " + val);
                    valid = false;
                }

                barcodes.push(val);
            });

            if (!valid) e.preventDefault();
        });
    }

});
