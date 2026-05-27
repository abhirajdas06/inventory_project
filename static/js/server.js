/* ============================================================
   static/js/server.js  —  Add Server page
============================================================ */

document.addEventListener("DOMContentLoaded", function () {

    console.log("server.js loaded");

    // ============================================================
    // HELPERS
    // ============================================================

    function getServerModel() {
        var el = document.getElementById("serverModelInput");
        return el ? el.value.trim() : "";
    }

    function getServerLocation() {
        var el = document.getElementById("serverLocationInput");
        return el ? el.value.trim() : "";
    }

    function getServerRefLocation() {
        var el = document.getElementById("serverRefLocationInput");
        return el ? el.value.trim() : "";
    }

    function resetRow(row) {
        // clear all inputs except readonly
        row.querySelectorAll("input").forEach(function (input) {
            if (input.hasAttribute("readonly")) return;
            input.value = "";
            input.classList.remove("error");
        });

        // reset all selects to first option
        row.querySelectorAll("select").forEach(function (sel) {
            sel.selectedIndex = 0;
        });

        // default qty = 1
        var qty = row.querySelector("input[name='comp_qty[]']");
        if (qty) qty.value = 1;

        // pre-fill model from server model
        var compModel = row.querySelector(".comp-model");
        if (compModel) compModel.value = getServerModel();

        // pre-fill location from server location
        var compLoc = row.querySelector(".comp-location");
        if (compLoc) compLoc.value = getServerLocation();

        // pre-fill ref location from server ref location
        var compRefLoc = row.querySelector(".comp-ref-location");
        if (compRefLoc) compRefLoc.value = getServerRefLocation();

        // remove stale error messages
        row.querySelectorAll(".serial-error, .barcode-error").forEach(function (el) {
            el.remove();
        });
    }

    // pre-fill all existing rows on page load
    function prefillExistingRows() {
        var serverModel    = getServerModel();
        var serverLoc      = getServerLocation();
        var serverRefLoc   = getServerRefLocation();

        document.querySelectorAll(".comp-model").forEach(function (inp) {
            if (!inp.value.trim()) inp.value = serverModel;
        });
        document.querySelectorAll(".comp-location").forEach(function (inp) {
            if (!inp.value.trim()) inp.value = serverLoc;
        });
        document.querySelectorAll(".comp-ref-location").forEach(function (inp) {
            if (!inp.value.trim()) inp.value = serverRefLoc;
        });
    }


    // ============================================================
    // SYNC — when server fields change, update all comp rows
    //         that still show the old synced value
    // ============================================================

    var prevModel   = getServerModel();
    var prevLoc     = getServerLocation();
    var prevRefLoc  = getServerRefLocation();

    var serverModelInput    = document.getElementById("serverModelInput");
    var serverLocationInput = document.getElementById("serverLocationInput");
    var serverRefLocInput   = document.getElementById("serverRefLocationInput");

    if (serverModelInput) {
        serverModelInput.addEventListener("input", function () {
            var newVal = serverModelInput.value.trim();
            document.querySelectorAll(".comp-model").forEach(function (inp) {
                if (inp.value.trim() === prevModel || inp.value.trim() === "") {
                    inp.value = newVal;
                }
            });
            prevModel = newVal;
        });
    }

    if (serverLocationInput) {
        serverLocationInput.addEventListener("input", function () {
            var newVal = serverLocationInput.value.trim();
            document.querySelectorAll(".comp-location").forEach(function (inp) {
                if (inp.value.trim() === prevLoc || inp.value.trim() === "") {
                    inp.value = newVal;
                }
            });
            prevLoc = newVal;
        });
    }

    if (serverRefLocInput) {
        serverRefLocInput.addEventListener("input", function () {
            var newVal = serverRefLocInput.value.trim();
            document.querySelectorAll(".comp-ref-location").forEach(function (inp) {
                if (inp.value.trim() === prevRefLoc || inp.value.trim() === "") {
                    inp.value = newVal;
                }
            });
            prevRefLoc = newVal;
        });
    }


    // ============================================================
    // ADD COMPONENT ROW
    // ============================================================
    document.addEventListener("click", function (e) {

        var btn = e.target.closest(".add-comp-row");
        if (!btn) return;

        var tbody = document.getElementById("compRows");
        if (!tbody) return;

        var firstRow = tbody.querySelector("tr");
        if (!firstRow) return;

        var newRow = firstRow.cloneNode(true);
        resetRow(newRow);

        tbody.appendChild(newRow);
        newRow.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });


    // ============================================================
    // REMOVE COMPONENT ROW
    // ============================================================
    document.addEventListener("click", function (e) {

        var btn = e.target.closest(".remove-comp");
        if (!btn) return;

        var tbody = document.getElementById("compRows");
        if (!tbody) return;

        var rows = tbody.querySelectorAll("tr");
        if (rows.length > 1) {
            btn.closest("tr").remove();
        }
    });


    // ============================================================
    // SERVICE TAG DUPLICATE CHECK
    // ============================================================
    var stInput  = document.getElementById("serviceTagInput");
    var stError  = document.getElementById("serviceTagError");
    var stDebounce;

    if (stInput) {
        stInput.addEventListener("blur", function () {

            clearTimeout(stDebounce);

            stDebounce = setTimeout(function () {

                var val = stInput.value.trim().toUpperCase();
                stInput.value = val;

                stInput.classList.remove("error");
                if (stError) stError.style.display = "none";

                if (!val) return;

                fetch("/servers/check-service-tag/?service_tag=" + encodeURIComponent(val))
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (data.exists) {
                            stInput.classList.add("error");
                            if (stError) stError.style.display = "block";
                        }
                    })
                    .catch(function (err) {
                        console.error("Service tag check error:", err);
                    });

            }, 300);
        });
    }


    // ============================================================
    // FORM VALIDATION
    // ============================================================
    var form = document.getElementById("serverForm");

    if (form) {
        form.addEventListener("submit", function (e) {

            var valid    = true;
            var barcodes = [];

            // service tag required + not duplicate
            if (stInput) {
                if (!stInput.value.trim()) {
                    stInput.classList.add("error");
                    valid = false;
                }
                if (stInput.classList.contains("error")) {
                    valid = false;
                }
            }

            // barcode uniqueness across cabinet + all component rows
            document.querySelectorAll(".barcode-check").forEach(function (input) {
                var val = input.value.trim().toUpperCase();
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

            // soft check — warn if no components
            var hasComp = false;
            document.querySelectorAll("input[name='comp_spare_type[]']").forEach(function (inp) {
                if (inp.value.trim()) hasComp = true;
            });

            if (!hasComp) {
                if (!confirm("No components added. Save server without components?")) {
                    valid = false;
                }
            }

            if (!valid) e.preventDefault();
        });
    }


    // ============================================================
    // INIT — prefill the default first row
    // ============================================================
    prefillExistingRows();

});