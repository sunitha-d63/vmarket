document.addEventListener("DOMContentLoaded", function () {
    const unitField = document.getElementById("id_unit");
    const weightField = document.getElementById("id_weight_options");

    if (!unitField || !weightField) return;

    function updateWeightOptions() {
        const unit = unitField.value;

        if (unit === "kg") weightField.value = "250G,500G,1KG,2KG,5KG";
        else if (unit === "g") weightField.value = "50G,100G,250G,500G";
        else if (unit === "litre") weightField.value = "200ML,500ML,1L,2L";
        else if (unit === "ml") weightField.value = "50ML,100ML,200ML,500ML";
        else if (unit === "piece") weightField.value = "1PC,2PC,6PC,12PC";
        else if (unit === "pack") weightField.value = "1PACK,2PACK,5PACK";
        else if (unit === "dozen") weightField.value = "1DOZEN,2DOZEN";
    }

    unitField.addEventListener("change", updateWeightOptions);
});
