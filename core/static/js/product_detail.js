document.addEventListener("DOMContentLoaded", () => {
    const weightSelector = document.getElementById("weightSelector");
    const dropdown = document.getElementById("weightDropdown");
    const weightHidden = document.getElementById("selectedWeight");
    const weightText = document.getElementById("selectedWeightText");

    const qtyInput = document.getElementById("quantityInput");
    const livePrice = document.getElementById("livePrice");
    const strikeMRP = document.querySelector(".text-decoration-line-through");
    const savingsText = document.querySelector(".text-success");

    const basePrice = parseFloat(document.getElementById("basePrice").value);
    const discountPrice = parseFloat(document.getElementById("discountPrice").value);
    const unit = document.getElementById("productUnit").value.toLowerCase();
    const offerActive = document.getElementById("isOfferActive").value === "True";
    const pricePerUnit = offerActive ? discountPrice : basePrice;

    // set default hidden select value to the displayed text
    if (weightText && weightHidden) {
        const defaultWeight = weightText.innerText.trim();
        if (defaultWeight) {
            weightHidden.value = defaultWeight;
            // ensure the corresponding <option> is selected (optional)
            Array.from(weightHidden.options).forEach(opt => {
                opt.selected = opt.value === defaultWeight;
            });
        }
    }

    function convertWeight(value) {
        const w = (value || "").toString().toUpperCase().trim();
        if (!w) return 1;

        // KG / G
        if (unit === "kg" || unit === "g") {
            if (w.endsWith("KG")) return parseFloat(w.replace("KG", ""));
            if (w.endsWith("G")) return parseFloat(w.replace("G", "")) / 1000;
        }

        // LITRE / ML
        if (unit === "litre" || unit === "ml") {
            if (w.endsWith("ML")) return parseFloat(w.replace("ML", "")) / 1000;
            if (w.endsWith("L")) return parseFloat(w.replace("L", ""));
        }

        // piece / pack
        if (unit === "piece" || unit === "pack") {
            const num = parseFloat(w.replace(/[^0-9]/g, ""));
            return num > 0 ? num : 1;
        }

        if (unit === "dozen") {
            const num = parseFloat(w.replace(/[^0-9]/g, ""));
            return num > 0 ? num * 12 : 12;
        }

        return 1;
    }

    function updatePriceUI() {
        const selectedWeight = weightText.innerText.trim();
        const qty = parseInt(qtyInput.value) || 1;
        const multiplier = convertWeight(selectedWeight);
        const finalPrice = pricePerUnit * multiplier * qty;
        if (livePrice) livePrice.textContent = "₹" + finalPrice.toFixed(2);
        if (strikeMRP) {
            const mrpTotal = basePrice * multiplier * qty;
            strikeMRP.textContent = "MRP: ₹" + mrpTotal.toFixed(2);
        }
        if (offerActive && savingsText) {
            const savingsPerUnit = basePrice - discountPrice;
            const totalSavings = savingsPerUnit * multiplier * qty;
            const percent = basePrice ? ((savingsPerUnit / basePrice) * 100).toFixed(0) : 0;
            savingsText.textContent = `You save ₹${totalSavings.toFixed(2)} (${percent}% OFF)`;
        }
    }
    weightSelector.addEventListener("click", (e) => {
        e.stopPropagation();
        dropdown.classList.toggle("d-none");
    });

    dropdown.querySelectorAll("li").forEach((li) => {
        li.addEventListener("click", (e) => {
            e.stopPropagation();
            const value = li.getAttribute("data-value");
            weightText.textContent = value;
            if (weightHidden) {
                weightHidden.value = value;
                Array.from(weightHidden.options).forEach(opt => opt.selected = opt.value === value);
            }
            dropdown.classList.add("d-none");
            updatePriceUI();
        });
    });

    document.addEventListener("click", () => dropdown.classList.add("d-none"));

    qtyInput.addEventListener("input", () => {
        if (qtyInput.value < 1) qtyInput.value = 1;
        updatePriceUI();
    });

    document.querySelector(".qty-btn.plus").addEventListener("click", () => {
        qtyInput.value = parseInt(qtyInput.value) + 1;
        updatePriceUI();
    });

    document.querySelector(".qty-btn.minus").addEventListener("click", () => {
        if (parseInt(qtyInput.value) > 1) {
            qtyInput.value = parseInt(qtyInput.value) - 1;
            updatePriceUI();
        }
    });
    updatePriceUI();
});
