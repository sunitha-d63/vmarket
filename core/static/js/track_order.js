document.addEventListener("DOMContentLoaded", () => {

    const orderData = document.getElementById("orderData");
    if (!orderData) return;

    const orderId = orderData.dataset.orderId;
    let driverLat = parseFloat(orderData.dataset.driverLat);
    let driverLon = parseFloat(orderData.dataset.driverLon);
    const custLat = parseFloat(orderData.dataset.custLat);
    const custLon = parseFloat(orderData.dataset.custLon);
    const createdTime = new Date(orderData.dataset.created).getTime();
    const expectedTime = new Date(orderData.dataset.expected).getTime();

    const map = L.map("map").setView([custLat, custLon], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png").addTo(map);

    let driverMarker = L.marker([driverLat, driverLon], {
        icon: L.divIcon({ html: "🚚", className: "truck-marker" })
    }).addTo(map);

    const etaBox = document.getElementById("etaBox");
    const liveLocationText = document.getElementById("liveLocationText");
    const progressFill = document.getElementById("progressFill");
    const truckIcon = document.getElementById("truckIcon");

    function haversine(lat1, lon1, lat2, lon2) {
        const R = 6371;
        const toRad = d => d * Math.PI / 180;
        const dLat = toRad(lat2 - lat1);
        const dLon = toRad(lon2 - lon1);

        return R * 2 * Math.atan2(
            Math.sqrt(
                Math.sin(dLat/2)**2 +
                Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                Math.sin(dLon/2)**2
            ),
            Math.sqrt(1 -
                (Math.sin(dLat/2)**2 +
                 Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                 Math.sin(dLon/2)**2)
            )
        );
    }

    function updateTracking(data) {
    driverLat = data.driver_lat;
    driverLon = data.driver_lon;

    driverMarker.setLatLng([driverLat, driverLon]);

    const distanceKm = haversine(driverLat, driverLon, custLat, custLon);
    const etaMinutes = Math.ceil((distanceKm / 20) * 60);
    window.latestDistanceKm = distanceKm;
    window.latestEtaMinutes = etaMinutes;

    etaBox.textContent = `🚚 ${distanceKm.toFixed(2)} km away — ETA ${etaMinutes} min`;
    const now = Date.now();
    const pct = Math.min(Math.max(((now - createdTime) / (expectedTime - createdTime)) * 100, 0), 100);

    progressFill.style.width = pct + "%";
    truckIcon.style.left = `calc(${pct}% - 20px)`;
if (distanceKm < 0.15) {   
    progressFill.style.width = "100%";
    truckIcon.style.left = "calc(100% - 20px)";
    if (!window.deliveryCompletedShown) {
        window.deliveryCompletedShown = true;

        document.getElementById("delayMessage").innerHTML = `
            🎉 <strong>Your order has been delivered!</strong><br>
            Thank you for choosing VetriMart.
        `;

        new bootstrap.Modal(document.getElementById("delayModal")).show();
    }
}
    fetch(`/reverse-geocode/?lat=${driverLat}&lon=${driverLon}`)

    .then(r => r.json())
    .then(loc => {
        const area = loc.address.suburb || loc.address.village || loc.address.road || "Unknown";
        const city = loc.address.city || loc.address.town || "";
        liveLocationText.innerHTML = `📍 <strong>Near ${area}, ${city}</strong>`;
    });
}

    function fetchLocation() {
        fetch(`/track-location/${orderId}/`)
        .then(r => r.json())
        .then(data => updateTracking(data));
    }

    fetchLocation();
    setInterval(fetchLocation, 5000);

    document.getElementById("deliveryTime").addEventListener("click", function () {

    const expected = new Date(orderData.dataset.expected);
    const created = new Date(orderData.dataset.created);

    const dist = window.latestDistanceKm;
    const eta  = window.latestEtaMinutes;

    let msg = `
      🚚 <strong>${dist.toFixed(2)} km</strong> away — ETA <strong>${eta} min</strong><br><br>
      📅 <strong>Expected Delivery:</strong> ${expected.toLocaleString()}<br><br>
    `;

    if (new Date() > expected) {
        msg += `<span style="color:red;font-weight:700;">⚠️ Delayed</span>`;
    } else {
        msg += `<span style="color:green;font-weight:700;">✔️ On Time</span>`;
    }

    document.getElementById("delayMessage").innerHTML = msg;
    new bootstrap.Modal(document.getElementById("delayModal")).show();
});

});

window.onload = function () {

    const deliveryTimeBtn = document.getElementById("deliveryTime");

    if (deliveryTimeBtn) {
        deliveryTimeBtn.style.textDecoration = "underline";
        deliveryTimeBtn.style.fontWeight = "bold";

        deliveryTimeBtn.addEventListener("click", function() {

            let msg = `
                🚚 <strong>${window.latestDistanceKm.toFixed(2)} km</strong> away — 
                ETA <strong>${window.latestEtaMinutes} min</strong><br><br>

                📅 <strong>Expected Delivery:</strong> 
                ${new Date(expectedTime).toLocaleString()}<br><br>
            `;

            if (Date.now() > expectedTime) {
                msg += `<strong style="color:red;">⚠ Delivery running late.</strong>`;
            } else {
                msg += `✔️ On time.`;
            }

            document.getElementById("delayMessage").innerHTML = msg;

            const modal = new bootstrap.Modal(document.getElementById("delayModal"));
            modal.show();
        });
    }
};
