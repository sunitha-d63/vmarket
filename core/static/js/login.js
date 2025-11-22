
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select").forEach(function (selectElement) {
        const wrapper = document.createElement("div");
        wrapper.className = "custom-select-wrapper";
        const display = document.createElement("div");
        display.className = "custom-select-display";
        display.innerText = selectElement.options[selectElement.selectedIndex].text;
        const optionBox = document.createElement("div");
        optionBox.className = "custom-select-options";
        Array.from(selectElement.options).forEach(option => {
            const opt = document.createElement("div");
            opt.className = "custom-select-option";
            opt.innerText = option.text;
            opt.dataset.value = option.value;

            if (option.selected) opt.classList.add("selected");

            opt.onclick = () => {
                selectElement.value = opt.dataset.value;
                display.innerText = opt.innerText;
                optionBox.style.display = "none";
                optionBox.querySelectorAll("div").forEach(o => o.classList.remove("selected"));
                opt.classList.add("selected");
            };

            optionBox.appendChild(opt);
        });

        display.onclick = () => {
            optionBox.style.display = optionBox.style.display === "block" ? "none" : "block";
        };

        selectElement.style.display = "none";

        selectElement.parentNode.insertBefore(wrapper, selectElement);
        wrapper.appendChild(selectElement);
        wrapper.appendChild(display);
        wrapper.appendChild(optionBox);
    });
});
