/* ============================================================
   static/js/harddisk.js  —  Add Hard Disk page
   NOTE: HardDisk has TWO barcode fields:
     - barcode[]       → main barcode
     - tray_barcode[]  → tray barcode
   Both use class="barcode-check" so barcode_check.js
   validates them automatically on blur.
   Form submit validation below checks both for in-form dupes.
============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    // ----------------------------------------
    // ADD ROW
    // ----------------------------------------
    document.addEventListener("click", function (e) {

        if (!e.target.closest(".add-row")) return;

        let tbody    = document.querySelector("#harddiskTable tbody");
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

        newRow.querySelectorAll(".serial-error, .barcode-error").forEach(el => el.remove());

        tbody.appendChild(newRow);
    });


    // ----------------------------------------
    // REMOVE ROW
    // ----------------------------------------
    document.addEventListener("click", function (e) {

        let removeBtn = e.target.closest(".remove");
        if (!removeBtn) return;

        let rows = document.querySelectorAll("#harddiskTable tbody tr");
        if (rows.length > 1) {
            removeBtn.closest("tr").remove();
        }
    });


    // ----------------------------------------
    // FORM VALIDATION
    // Checks BOTH barcode[] and tray_barcode[] since
    // both carry class="barcode-check"
    // ----------------------------------------
    let form = document.getElementById("harddiskForm");

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
