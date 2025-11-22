document.addEventListener("DOMContentLoaded", () => {

    const plusBtns = document.querySelectorAll(".qty-btn.plus");
    const minusBtns = document.querySelectorAll(".qty-btn.minus");
    const qtyInputs = document.querySelectorAll(".qty-input");

    // CSRF helper for Django
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let cookie of cookies) {
                cookie = cookie.trim();
                if (cookie.startsWith(name + "=")) {
                    cookieValue = decodeURIComponent(cookie.split("=")[1]);
                    break;
                }
            }
        }
        return cookieValue;
    }

    plusBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const input = btn.closest(".qty-control").querySelector(".qty-input");
            input.value = parseInt(input.value) + 1;
            updateRow(input);
        });
    });

    minusBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const input = btn.closest(".qty-control").querySelector(".qty-input");
            let val = parseInt(input.value);
            if (val > 1) {
                input.value = val - 1;
                updateRow(input);
            }
        });
    });

    qtyInputs.forEach(input => {
        input.addEventListener("input", () => {
            if (input.value < 1) input.value = 1;
            updateRow(input);
        });
    });

    function updateRow(inputEl) {
        const card = inputEl.closest(".cart-item");

        const unitPrice = parseFloat(card.querySelector(".unit-price").value);
        const weightMult = parseFloat(card.querySelector(".weight-mult").value);

        const qty = parseInt(inputEl.value);
        const id = inputEl.dataset.id;

        const priceEl = document.getElementById(`price-${id}`);
        const finalPrice = unitPrice * weightMult * qty;

        priceEl.innerText = finalPrice.toFixed(2);

        // -------------------------
        // GUEST USER (session cart)
        // -------------------------
        if (card.classList.contains("guest-item")) {

            const pid = card.dataset.pid;
            const weight = card.dataset.weight;

            fetch("/update-guest-cart/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": getCookie("csrftoken")
                },
                body: `product_id=${pid}&weight=${weight}&qty=${qty}`
            })
            .then(res => res.json())
            .then(() => {
                updateTotals();
            });

            return; // Exit here
        }

        // -------------------------
        // LOGGED IN USER (database)
        // -------------------------
        fetch(`/update-cart-qty/${id}/${qty}/`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    updateTotals();
                }
            });
    }

    function updateTotals() {
        let subtotal = 0;

        document.querySelectorAll(".item-total span").forEach(el => {
            subtotal += parseFloat(el.innerText);
        });

        const tax = subtotal * 0.05;
        const total = subtotal + tax;

        document.getElementById("subtotal").innerText = subtotal.toFixed(2);
        document.getElementById("tax").innerText = tax.toFixed(2);
        document.getElementById("total").innerText = total.toFixed(2);
    }
});
