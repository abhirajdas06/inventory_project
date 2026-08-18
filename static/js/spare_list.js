window.addEventListener("load", function () {

    // 🔥 INLINE EDIT SAVE
    document.querySelectorAll(".editable").forEach(input => {

        input.addEventListener("keypress", function(e){

            if(e.key === "Enter"){

                let row = this.closest("tr");
                let id = row.dataset.id;
                let field = this.dataset.field;
                let value = this.value;

                fetch("/inventory/update-spare/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-CSRFToken": getCSRFToken()
                    },
                    body: `id=${id}&field=${field}&value=${value}`
                })
                .then(res => res.json())
                .then(data => {
                    if(data.success){
                        this.style.background = "#d4edda"; // green flash
                        setTimeout(()=> this.style.background = "", 500);
                    }
                });
            }

        });

    });

    // 🔥 MODAL HANDLER
    document.querySelectorAll(".audit-btn").forEach(btn => {
        btn.addEventListener("click", function(){
            showModal("Audit");
        });
    });

    document.querySelectorAll(".stockout-btn").forEach(btn => {
        btn.addEventListener("click", function(){
            showModal("Stock Out");
        });
    });

    function showModal(title){
        document.getElementById("modalTitle").innerText = title;

        let modal = new bootstrap.Modal(document.getElementById('actionModal'));
        modal.show();
    }

});


// CSRF helper
function getCSRFToken() {
    return document.cookie.split('; ')
        .find(row => row.startsWith('csrftoken'))
        ?.split('=')[1];
}
