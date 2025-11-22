document.addEventListener("DOMContentLoaded", function () {
    const timerElement = document.getElementById("countdownTimer");
    if (!timerElement) return;

    const etaString = timerElement.dataset.eta;
    const deliveryTime = new Date(etaString).getTime();

    if (isNaN(deliveryTime)) {
        timerElement.innerHTML = "Invalid delivery time!";
        return;
    }

    function updateTimer() {
        const now = Date.now();
        const distance = deliveryTime - now;

        if (distance <= 0) {
            timerElement.innerHTML = "Delivered or arriving now!";
            clearInterval(interval);
            return;
        }

        const hours = Math.floor((distance / (1000 * 60 * 60)) % 24);
        const minutes = Math.floor((distance / (1000 * 60)) % 60);
        const seconds = Math.floor((distance / 1000) % 60);

        timerElement.innerHTML = `⏳ ${hours}h ${minutes}m ${seconds}s remaining`;
        timerElement.classList.add("animate");
        setTimeout(() => timerElement.classList.remove("animate"), 300);
    }

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
});

document.addEventListener("DOMContentLoaded", function () {
    const etaElement = document.getElementById("deliveryData");
    const etaISO = etaElement?.dataset.eta;

    const timerElement = document.getElementById("countdownTimer");

    if (!etaISO) {
        timerElement.innerHTML = "Estimated arrival time will be available soon.";
        return;
    }

    const deliveryTime = new Date(etaISO).getTime();
    function updateTimer() {
        const now = new Date().getTime();
        const diff = deliveryTime - now;

        if (isNaN(deliveryTime)) {
            timerElement.innerHTML = "Invalid delivery time!";
            return;
        }

        if (diff <= 0) {
            timerElement.innerHTML = "🎉 Out for delivery soon!";
            clearInterval(interval);
            return;
        }

        const h = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const m = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const s = Math.floor((diff % (1000 * 60)) / 1000);

        timerElement.innerHTML = `⏳ ${h}h ${m}m ${s}s remaining`;
        timerElement.classList.add("animate");
        setTimeout(() => timerElement.classList.remove("animate"), 300);
    }

    updateTimer();
    const interval = setInterval(updateTimer, 1000);

    const fill = document.getElementById("progressFill");
    const truck = document.getElementById("truckIcon");

    function updateTrackingProgress() {
        const now = new Date().getTime();
        let progress = ((now - (deliveryTime - (2 * 60 * 60 * 1000))) / (2 * 60 * 60 * 1000)) * 100;
        if (progress < 0) progress = 0;
        if (progress > 100) progress = 100;

        fill.style.width = progress + "%";
        truck.style.left = progress + "%";
    }

    setInterval(updateTrackingProgress, 1000);
    updateTrackingProgress();
});
