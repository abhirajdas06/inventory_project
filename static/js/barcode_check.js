/* ============================================================
   static/js/barcode_check.js
   Universal barcode duplicate checker.
   Include this ONE file in base.html — it works across
   every add/edit page automatically.
   REPLACES all individual serial-check logic in:
     spare.js, card.js, cpu.js, memory.js, sfp.js,
     railkit.js, harddisk.js, controller.js
============================================================ */

(function () {

    'use strict';

    const ENDPOINT = '/spare/check-barcode/';
    const DEBOUNCE_MS = 300;

    let debounceTimer;

    // ----------------------------------------
    // ATTACH ON DOCUMENT READY (works for all pages)
    // ----------------------------------------
    document.addEventListener('DOMContentLoaded', function () {
        attachBarcodeCheck();
    });

    // ----------------------------------------
    // BARCODE CHECK ON BLUR
    // Targets any input with class "barcode-check"
    // ----------------------------------------
    function attachBarcodeCheck() {

        document.addEventListener('blur', function (e) {

            if (!e.target.classList.contains('barcode-check')) return;

            clearTimeout(debounceTimer);

            debounceTimer = setTimeout(() => {

                let input   = e.target;
                let barcode = input.value.trim().toUpperCase();
                input.value = barcode;

                // clear previous state
                input.classList.remove('error');
                clearError(input);

                if (!barcode) return;

                fetch(`${ENDPOINT}?barcode=${encodeURIComponent(barcode)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.exists) {
                            input.classList.add('error');
                            showError(input, 'Duplicate barcode');
                        }
                    })
                    .catch(() => {});

            }, DEBOUNCE_MS);

        }, true);  // capture phase so it fires before anything else
    }

    function showError(input, msg) {
        clearError(input);
        let err = document.createElement('div');
        err.className   = 'barcode-error serial-error';   // serial-error keeps your CSS styling
        err.textContent = msg;
        input.parentNode.appendChild(err);
    }

    function clearError(input) {
        let existing = input.parentNode.querySelector('.barcode-error');
        if (existing) existing.remove();
    }

})();
