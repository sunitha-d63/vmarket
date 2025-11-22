
const catRow = document.getElementById("categoryRow");
const btnLeft = document.querySelector(".cat-arrow-left");
const btnRight = document.querySelector(".cat-arrow-right");

btnLeft.addEventListener("click", () => {
    catRow.scrollBy({ left: -300, behavior: "smooth" });
});

btnRight.addEventListener("click", () => {
    catRow.scrollBy({ left: 300, behavior: "smooth" });
});
function revealOnScroll() {
    document.querySelectorAll(".fade-section").forEach(sec => {
        let rect = sec.getBoundingClientRect().top;
        if (rect < window.innerHeight - 80) {
            sec.classList.add("visible");
        }
    });
}
window.addEventListener("scroll", revealOnScroll);
revealOnScroll();
document.querySelectorAll(".magnet").forEach(btn => {
    btn.addEventListener("mousemove", e => {
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        btn.style.transform = `translate(${x * 0.1}px, ${y * 0.1}px)`;
    });
    btn.addEventListener("mouseleave", () => {
        btn.style.transform = "translate(0,0)";
    });
});

document.querySelectorAll(".tilt-card").forEach(card => {
    card.addEventListener("mousemove", e => {
        const rect = card.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;
        const tiltX = (y - 0.5) * 10;
        const tiltY = (x - 0.5) * -10;
        card.style.transform = `rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
    });
    card.addEventListener("mouseleave", () => {
        card.style.transform = "rotateX(0) rotateY(0)";
    });
});
window.addEventListener("scroll", () => {
    document.querySelectorAll(".parallax").forEach(img => {
        let offset = window.scrollY * 0.15;
        img.style.transform = `translateY(${offset}px)`;
    });
});


  const slider = document.getElementById("categorySlider");

  document.querySelector(".cat-arrow-right").onclick = () => {
    slider.scrollBy({ left: 300, behavior: "smooth" });
  };

  document.querySelector(".cat-arrow-left").onclick = () => {
    slider.scrollBy({ left: -300, behavior: "smooth" });
  };

