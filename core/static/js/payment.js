document.addEventListener("DOMContentLoaded", function () {
  function setupDropdown(selectedDisplayId, listId, hiddenSelectId) {
    const display = document.getElementById(selectedDisplayId);
    const list = document.getElementById(listId);
    const hiddenSelect = document.getElementById(hiddenSelectId);
    display.addEventListener("click", () => {
      list.classList.toggle("d-none");
    });
    list.querySelectorAll("li").forEach((li) => {
      li.addEventListener("click", function () {
        display.textContent = this.textContent;
        hiddenSelect.value = this.dataset.value;

        list.classList.add("d-none");
      });
    });
    document.addEventListener("click", function (e) {
      if (!display.closest(".custom-weight-dropdown").contains(e.target)) {
        list.classList.add("d-none");
      }
    });
  }

  setupDropdown("selectedDeliveryZoneDisplay", "deliveryZoneList", "deliveryZoneSelect");
  setupDropdown("selectedDeliverySlotDisplay", "deliverySlotList", "deliverySlotSelect");
});
function getCSRFToken() {
  const cookie = document.cookie.match("(^|;)\\s*csrftoken\\s*=\\s*([^;]+)");
  return cookie ? cookie.pop() : "";
}

document.addEventListener("DOMContentLoaded", () => {

  const mapEl = document.getElementById("map");
  let map = null;
  let marker = null;

  if (mapEl) {
    try {
      map = L.map(mapEl).setView([11.4064, 76.6932], 13);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);
    } catch (err) {
      console.error("Leaflet init fail:", err);
      map = null;
    }
  }

  function placeMarker(lat, lon) {
    if (!map) return;
    if (marker) marker.remove();
    marker = L.marker([lat, lon]).addTo(map);
    map.setView([lat, lon], 14);

    const latEl = document.getElementById("id_latitude");
    const lonEl = document.getElementById("id_longitude");
    if (latEl) latEl.value = lat;
    if (lonEl) lonEl.value = lon;
  }

  async function reverseGeocode(lat, lon) {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lon}`
      );
      const data = await res.json();
      const street = document.getElementById("id_street_address");
      const city = document.getElementById("id_city");
      if (street)
        street.value = data.address?.road || data.address?.pedestrian || "";
      if (city)
        city.value =
          data.address?.city ||
          data.address?.town ||
          data.address?.village ||
          "";
    } catch (e) {
      console.warn("reverseGeocode failed", e);
    }
  }

  async function sendFeasibilityCheck(lat, lon) {
    const zoneSelect = document.getElementById("deliveryZoneSelect");
    const slotSelect = document.getElementById("deliverySlotSelect");

    const msgBox = document.getElementById("deliveryFeasibilityMsg");
    const etaPreview = document.getElementById("expectedTimePreview");

    if (!zoneSelect || !slotSelect) return;
    if (!zoneSelect.value || !slotSelect.value) return;

    try {
      const response = await fetch(CHECK_DELIVERY_URL, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCSRFToken(),
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          zone_id: zoneSelect.value,
          slot: slotSelect.value,
          latitude: lat,
          longitude: lon,
        }),
      });

      const data = await response.json();

      if (data.status === "on_time") {
        msgBox.innerHTML = `<div class="alert alert-success py-2 mb-1">${data.message}</div>`;
        etaPreview.innerHTML = `<span class="text-success fw-bold">ETA: ${data.eta}</span>`;
      } else {
        msgBox.innerHTML = `<div class="alert alert-warning py-2 mb-1">${data.message}</div>`;
        etaPreview.innerHTML = `<span class="text-danger fw-bold">ETA: ${data.eta}</span>`;
      }
    } catch (e) {
      msgBox.innerHTML = `<div class="alert alert-danger py-2 mb-0">Unable to check delivery.</div>`;
    }
  }


  const detectBtn = document.getElementById("detectLocationBtn");
  if (detectBtn) {
    detectBtn.addEventListener("click", () => {
      const status = document.getElementById("locationStatus");

      if (!navigator.geolocation) {
        status.textContent = "Geolocation not supported.";
        return;
      }

      status.textContent = "Detecting location…";

      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          placeMarker(lat, lon);
          status.textContent = " Location detected.";
          await reverseGeocode(lat, lon);
          await sendFeasibilityCheck(lat, lon);
        },
        () => {
          status.textContent = "Could not retrieve location.";
        }
      );
    });
  }

  if (map) {
    map.on("click", async (e) => {
      const { lat, lng } = e.latlng;
      placeMarker(lat, lng);
      await reverseGeocode(lat, lng);
      await sendFeasibilityCheck(lat, lng);
    });
  }

  document.querySelectorAll("#deliveryZoneList li").forEach((li) => {
    li.addEventListener("click", () => {
      const hidden = document.getElementById("deliveryZoneSelect");
      hidden.value = li.dataset.value;

      document.getElementById("selectedDeliveryZoneDisplay").textContent =
        li.textContent;

      if (li.dataset.lat && li.dataset.lon) {
        placeMarker(li.dataset.lat, li.dataset.lon);
      }

      const lat = document.getElementById("id_latitude").value;
      const lon = document.getElementById("id_longitude").value;

      if (lat && lon) sendFeasibilityCheck(lat, lon);
    });
  });

  document.querySelectorAll("#deliverySlotList li").forEach((li) => {
    li.addEventListener("click", () => {
      const hidden = document.getElementById("deliverySlotSelect");
      hidden.value = li.dataset.value;

      document.getElementById("selectedDeliverySlotDisplay").textContent =
        li.textContent;

      const lat = document.getElementById("id_latitude").value;
      const lon = document.getElementById("id_longitude").value;

      if (lat && lon) sendFeasibilityCheck(lat, lon);
    });
  });

  const payButton = document.getElementById("rzp-button1");
  const formEl = document.getElementById("paymentForm");
  const errorBox = document.getElementById("formErrorBox");

  payButton.disabled = false; 

  const requiredFields = [
    "id_full_name",
    "id_email",
    "id_phone",
    "id_street_address",
    "id_city",
    "deliveryZoneSelect",
    "deliverySlotSelect",
  ];

  function checkFormFilled(showError = false) {
    let allFilled = true;
    let missing = [];
    let invalidFields = [];

    for (let id of requiredFields) {
      const el = document.getElementById(id);
      if (!el || !el.value.trim()) {
        allFilled = false;
        missing.push(id);
      } else if (id === "id_phone") {
        const phoneValue = el.value.trim();
        const phonePattern = /^[0-9]{10}$/;
        if (!phonePattern.test(phoneValue)) {
          allFilled = false;
          invalidFields.push("Phone number must be exactly 10 digits.");
        }
      }
    }

    if (payButton) {
      payButton.disabled = !allFilled;
      payButton.classList.toggle("btn-success", allFilled);
      payButton.classList.toggle("btn-secondary", !allFilled);
      payButton.style.cursor = allFilled ? "pointer" : "not-allowed";
    }

    if (!allFilled && showError) {
      let errorMsg = "";
      if (missing.length > 0)
        errorMsg += "Please fill all required fields.<br>";
      if (invalidFields.length > 0) errorMsg += invalidFields.join("<br>");
      errorBox.innerHTML = `<div class="alert alert-danger py-2 mb-2"> ${errorMsg}</div>`;
    } else {
      errorBox.innerHTML = "";
    }

    return allFilled;
  }

  requiredFields.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", () => checkFormFilled());
      el.addEventListener("change", () => checkFormFilled());
    }
  });
  checkFormFilled();

 

  if (payButton && formEl) {
    payButton.addEventListener("click", function (e) {
      e.preventDefault();

      if (!checkFormFilled(true)) {
        errorBox.innerHTML = `<div class="alert alert-danger">⚠ Please fill all required fields</div>`;
        return;
      }

      const fd = new FormData(formEl);

      fetch(PAYMENT_PAGE_URL, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCSRFToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: fd,
      })
        .then((r) => r.json())
        .then((data) => {
          if (!data || data.status !== "created") {
            const message = data?.message
              ? JSON.stringify(data.message)
              : "Form validation failed.";
            errorBox.innerHTML = `<div class="alert alert-danger">${message}</div>`;
            return;
          }

          const options = {
            key: data.key,
            amount: data.amount,
            currency: "INR",
            name: "VetriMart",
            order_id: data.razorpay_order_id,
            handler: function (response) {
              fetch(VERIFY_URL, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": getCSRFToken(),
                },
                body: JSON.stringify({
                  razorpay_payment_id: response.razorpay_payment_id,
                  razorpay_order_id: response.razorpay_order_id,
                  razorpay_signature: response.razorpay_signature,
                  order_id: data.order_id,
                }),
              })
                .then((r) => r.json())
                .then((result) => {
                  if (result.status === "success") {
                    new bootstrap.Modal(
                      document.getElementById("paymentSuccessModal")
                    ).show();
                    setTimeout(
                      () =>
                        (window.location.href = `/order-confirmation/${result.order_id}/`),
                      1500
                    );
                  } else {
                    document.getElementById("paymentErrorMsg").textContent =
                      result.message || "Payment verification failed.";
                    new bootstrap.Modal(
                      document.getElementById("paymentErrorModal")
                    ).show();
                  }
                })
                .catch(() => {
                  document.getElementById("paymentErrorMsg").textContent =
                    "Server error during verification.";
                  new bootstrap.Modal(
                    document.getElementById("paymentErrorModal")
                  ).show();
                });
            },
            prefill: {
              name: document.getElementById("id_full_name")?.value || "",
              email: document.getElementById("id_email")?.value || "",
              contact: document.getElementById("id_phone")?.value || "",
            },
            theme: { color: "#4a5f76" },
          };

          new Razorpay(options).open();
        })
        .catch(() => {
          errorBox.innerHTML = `<div class="alert alert-danger">Server error. Try again.</div>`;
        });
    });
  }

});  

