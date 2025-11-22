function setupDropdown(displayId, listId, selectId, onSelectCallback = null) {

    const display = document.getElementById(displayId);
    const list = document.getElementById(listId);
    const select = document.getElementById(selectId);

    display.addEventListener("click", () => {
        list.classList.toggle("d-none");
    });

    list.querySelectorAll("li").forEach(li => {
        li.addEventListener("click", () => {

            display.innerText = li.innerText;
            select.value = li.dataset.value;

            list.classList.add("d-none");

            if (onSelectCallback) onSelectCallback(li);
        });
    });
}

let map, marker;
const etaBox = document.getElementById("editEtaMessage");

document.addEventListener("DOMContentLoaded", function () {

    const orderData = document.getElementById("orderData");
    let lat = parseFloat(orderData.dataset.lat);
    let lon = parseFloat(orderData.dataset.lon);

    map = L.map("map").setView([lat, lon], 14);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")
        .addTo(map);

    marker = L.marker([lat, lon], { draggable: true }).addTo(map);

    marker.on("dragend", (e) => {
        const pos = e.target.getLatLng();
        updateCoords(pos.lat, pos.lng);
        checkFeasibility();
    });

    map.on("click", (e) => {
        marker.setLatLng(e.latlng);
        updateCoords(e.latlng.lat, e.latlng.lng);
        checkFeasibility();
    });

    document.getElementById("detectLocationBtn").onclick = () => {
        navigator.geolocation.getCurrentPosition(pos => {
            const la = pos.coords.latitude;
            const lo = pos.coords.longitude;
            marker.setLatLng([la, lo]);
            map.setView([la, lo], 14);
            updateCoords(la, lo);
            checkFeasibility();
        });
    };
});

function updateCoords(lat, lon) {
    document.getElementById("id_latitude").value = lat;
    document.getElementById("id_longitude").value = lon;
    reverseGeocode(lat, lon);
}

async function reverseGeocode(lat, lon) {
    try {
        const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`
        );
        const data = await res.json();

        const street = data.address.road || "";
        const city = data.address.city || data.address.town || data.address.village || "";

        if (street) document.getElementById("id_street_address").value = street;
        if (city) document.getElementById("id_city").value = city;

    } catch {}
}

async function checkFeasibility() {

    const zoneId = document.getElementById("editDeliveryZoneSelect").value;
    const slot = document.getElementById("editDeliverySlotSelect").value;
    const lat = document.getElementById("id_latitude").value;
    const lon = document.getElementById("id_longitude").value;

    if (!zoneId || !slot || !lat || !lon) {
        etaBox.innerHTML = "";
        return;
    }

    try {
        const res = await fetch("/check-delivery-feasibility/", {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": document.cookie.match(/csrftoken=([^;]+)/)[1]
            },
            body: new URLSearchParams({
                zone_id: zoneId,
                slot: slot,
                latitude: lat,
                longitude: lon
            })
        });

        const data = await res.json();

        if (!data.eta) {
            etaBox.innerHTML = `<span class="text-danger">Unable to calculate ETA.</span>`;
            return;
        }

        etaBox.innerHTML = `
            <div class="alert alert-${data.status === "on_time" ? "success" : "warning"}">
                Delivery scheduled for <b>${data.day_label || "Today"}</b>, arriving around 
                <b>${data.eta}</b>
                <span class="text-muted">(Distance ${data.distance_km} km)</span>
            </div>
        `;

    } catch (err) {
        etaBox.innerHTML = `<span class="text-danger">Server error checking ETA.</span>`;
    }
}

setupDropdown(
    "editSelectedDeliveryZone",
    "editDeliveryZoneList",
    "editDeliveryZoneSelect",
    (li) => {
        updateCoords(parseFloat(li.dataset.lat), parseFloat(li.dataset.lon));
        checkFeasibility();
    }
);

setupDropdown(
    "editSelectedSlot",
    "editDeliverySlotList",
    "editDeliverySlotSelect",
    () => checkFeasibility()
);
