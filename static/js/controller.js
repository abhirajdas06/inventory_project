/* ============================================================
   static/js/controller.js  —  Add Controller page
   Cabinet barcode + all component barcodes validated via
   barcode_check.js (class="barcode-check").
   This file handles: add/remove rows + form validation.
============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    console.log("controller.js loaded");

    // ----------------------------------------
    // ADD COMPONENT ROW
    // ----------------------------------------
    document.addEventListener("click", function (e) {

        if (!e.target.closest(".add-component-row")) return;

        let tbody    = document.querySelector("#componentRows");
        let firstRow = tbody.querySelector("tr");
        let newRow   = firstRow.cloneNode(true);

        newRow.querySelectorAll("input").forEach(input => {
            input.value = "";
            input.classList.remove("error");
        });

        newRow.querySelectorAll("select").forEach(sel => {
            sel.selectedIndex = 0;
        });

        let qty = newRow.querySelector("input[name='comp_qty[]']");
        if (qty) qty.value = 1;

        newRow.querySelectorAll(".serial-error, .barcode-error").forEach(el => el.remove());

        tbody.appendChild(newRow);
    });


    // ----------------------------------------
    // REMOVE COMPONENT ROW
    // ----------------------------------------
    document.addEventListener("click", function (e) {

        let removeBtn = e.target.closest(".remove-component");
        if (!removeBtn) return;

        let rows = document.querySelectorAll("#componentRows tr");
        if (rows.length > 1) {
            removeBtn.closest("tr").remove();
        }
    });


    // ----------------------------------------
    // FORM VALIDATION
    // Checks cabinet barcode + all component barcodes
    // ----------------------------------------
    let form = document.getElementById("controllerForm");

    if (form) {
        form.addEventListener("submit", function (e) {

            let valid    = true;
            let barcodes = [];

            // check all barcode-check inputs (cabinet + components)
            document.querySelectorAll(".barcode-check").forEach(input => {

                let val = input.value.trim().toUpperCase();
                input.value = val;

                if (!val) return;

                // server-detected duplicate (red border set by barcode_check.js)
                if (input.classList.contains("error")) {
                    valid = false;
                }

                // within-form duplicate
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