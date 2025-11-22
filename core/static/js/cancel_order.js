
document.addEventListener("DOMContentLoaded", function () {

    const dd = document.getElementById("reasonDropdown");
    const selectedBox = dd.querySelector(".dropdown-selected");
    const selectedText = dd.querySelector(".selected-text");
    const list = dd.querySelector(".dropdown-list");
    const options = list.querySelectorAll("li");
    const hiddenInput = document.getElementById("reasonInput");
    const otherWrapper = document.getElementById("other-reason-wrapper");

    selectedBox.addEventListener("click", () => {
        dd.classList.toggle("open");
    });
    options.forEach(option => {
        option.addEventListener("click", () => {

            selectedText.textContent = option.textContent;
            hiddenInput.value = option.dataset.value;

            dd.classList.remove("open");

            if (option.dataset.value === "other") {
                otherWrapper.style.display = "block";
            } else {
                otherWrapper.style.display = "none";
                document.getElementById("id_other_reason").value = "";
            }

        });
    });
    document.addEventListener("click", (e) => {
        if (!dd.contains(e.target)) {
            dd.classList.remove("open");
        }
    });
});

